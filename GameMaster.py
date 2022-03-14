import copy
import role, item, story
import logbook, questSystem
import speaker, tools

from battleSystem import BattleContext

class GameMaster():
    """The Master of the game"""

    godGift = True
    advGroup = {}
    hordeGroup = {}
    money = 0

    def __init__(self):

        self.bookCase = story.BookCase.FromJson(self, tools.ParseJson("library"))
        self.ReadBook("TerraHill")

        self.advEnroll = tools.CopyEntities(self.adventurers[:3])
        self.advGroup = tools.RandomDict(self.advEnroll, 20)

        self.battleContext = BattleContext()
        self.questSystem = questSystem.QuestSytem()

        speaker.InitTimer()
        speaker.Write(str(self))

        return

    def __str__(self):
        return "\nBattle state:\n" + "Adventurers:\n" + self.AdventurersToString() + "Horde:\n" + self.HordeToString()

    def AdventurersToString(self):
        adventurers = ""

        for adv in self.advGroup.values():
            adventurers += "  " + str(adv) + "\n\n"

        return adventurers

    def HordeToString(self):
        horde = ""

        for monster in self.hordeGroup.values():
            horde += "  " + str(monster) + "\n\n"

        return horde

    def ReadBook(self, book):

        self.bookCase.SetCurrentBook(book)

        bookInput = tools.ParseJson(book + "Book")
        bookInput.pop("StoryBook")

        # ENTITY STORAGE
        self.horde = []
        self.adventurers = []

        for key, value in bookInput.items():
            entity = role.Role.FromJson(self, key, value)
            if (entity.adventurer is True):
                self.adventurers.append(entity)
            else:
                self.horde.append(entity)

        self.entities = self.horde + self.adventurers

    def AdventurersAlive(self):
        return len(self.advGroup) > 0

    def HordeAlive(self):
        return len(self.hordeGroup) > 0

    def Fighting(self):
        return self.AdventurersAlive() and self.HordeAlive()

    def AssertEntityDead(self, key, entity):
        ## Check if entity is alive
        if not entity.Alive():
            ## Remove entity from the game
            self.combattants.pop(key)

            adv = self.advGroup.pop(key, None)
            if adv is not None:
                tools.Pop(self.advEnroll, adv.getName(), lambda name, a: name == a.getName())

            self.hordeGroup.pop(key, None)

            return True

    def Pause(self, turn):
        speaker.Speak("\n=== Turn " + str(turn) + " finished. \n  - Tap 'info' to see state, else tap anything \n  - Tap 'help' to seek lucky Help\n  - ENTER to continue\n ")
        self.PauseInput()

    def PauseInput(self, help=True):
        entry = speaker.Input()

        if (entry == 'info'): # Battle info (entity stats)
            speaker.Write(str(self))
            if help:
                speaker.Speak("Tap 'help' or ENTER:")
            else:
                speaker.Speak("Tap ENTER:")
            self.PauseInput(help)

        elif (help and entry == 'help'): # Get a chance to have a special rewards, cost is patience
            speaker.Write("You ask for help...")
            speaker.time.sleep(3)
            if self.GodGift():
                speaker.Write("A god hears you, and gives 10HP for all your adventurers.")
            else:
                speaker.Write("Sorry but, you wait for nothing.")
            speaker.Speak("Tap 'info' or ENTER:")
            self.PauseInput(False)

        print()

    def EndTurn(self, key):
        # move entity to the end of the list
        if key in self.combattants.keys():
            self.combattants.move_to_end(key)

    def GameLoop(self):
        journey = True
        while journey and self.AdventurersAlive() :

            # QUEST
            self.questSystem.Check(self)

            # STORY
            st = self.bookCase.book.GetRandomStory()
            self.StoryHappens(st)

            # BATTLE

            logbook.battleWon += 1 # battleWon = -1 at beginning
            
            self.Battle() # battle event
            self.EndBattle() # a party won

        # END
        speaker.Write(".")
        speaker.Write(".")
        speaker.Write(".")
        speaker.Write("Your adventure stop here, you successed " + str(logbook.battleWon) + " battles !\n")

    def StoryHappens(self, storyTuple):
        speaker.Speak()
        speaker.Write(storyTuple[0])
        storyTuple[1].Happens(self)


    def SetBattleContext(self):

        hordeGroup = self.battleContext.DefineHordeGroup(self)

        # Define the order of the entities in battle
        self.advGroup = tools.RandomDict(self.advEnroll, 20)
        self.hordeGroup = tools.RandomDict(hordeGroup, 20, 0.1)
        merge = tools.MergeDict(self.advGroup, self.hordeGroup)
        
        self.combattants = tools.Reorder(merge)

        # Improve adventurer strenght each round
        for adv in self.advGroup.values():
            adv.baseArmorBreaker = 20 + logbook.battleWon

        # Send a signal for battle beginning
        for entity in self.combattants.values():
            entity.OnBattleBegins()

        return

    def Battle(self):

        self.SetBattleContext()

        #Introduction sentences
        speaker.Write("A horde appears !")
        speaker.Input()
        speaker.Write(str(self))
        speaker.WriteInput("\n ... Tap ENTER to begin battle")
        speaker.Speak("\n")

        # Battle loop
        prevTurn = 0

        while(self.Fighting()):
            key, entity = self.combattants.items()[0]
            # Check entity life
            if self.AssertEntityDead(key, entity):
                break
            # Check new turn condition
            elif (entity.turn is not prevTurn):
                self.Pause(prevTurn)
                prevTurn += 1

            # ENTITY TURN
            entity.Play()

            self.EndTurn(key) 

        # WINNER
        if self.AdventurersAlive():
            speaker.Speak("\n===== YOU WON THE FIGHT ! =====")
        else:
            speaker.Speak("\n===== HORDE WON THE FIGHT ! YOU LOSE... =====")

        self.battleContext.horde.clear() # Clear battleContext horde group
        speaker.Input("")

        return

    def EndBattle(self):
        self.battleContext.ToDefault()
        return

    def NewRandomMember(self):
        '''Get a random member which is not enrolled'''
        name = []
        for adventurer in self.advEnroll:
            name.append(adventurer.getName())

        self.adventurers = tools.RandomizeList(self.adventurers)
        for adventurer in self.adventurers:
            if adventurer.getName() in name:
                continue
            self.advEnroll.append(tools.CopyEntity(adventurer))
            return adventurer

        return None

    def GiveItemRandom(self, item, groupIndex = 0):
        '''groupIndex : 0 -adventurers 1- horde 2- all'''
        if groupIndex == 0:
            tools.RandomItem(self.advGroup)[1].GiveItem(item)
        elif groupIndex == 1:
            tools.RandomItem(self.hordeGroup)[1].GiveItem(item)
        else:
            tools.RandomItem(self.combattants)[1].GiveItem(item)

    def GetAdventurer(self, name):
        # Find an adventurer by its name
        for adv in self.advGroup.values():
            if name.lower() == adv.getName().lower():
                return adv
                
        return None

    def SelectAdventurer(self, recall = False):
        '''Ask player to chose an adventurer'''
        if not recall:
            entry = speaker.WriteInput("Chose an adventurer to give the item, tap 'info' to see team state : ")
        else:
            entry = speaker.WriteInput("Tap the adventurer's name : ")

        if entry == "info":
            speaker.Speak(self.AdventurersToString())
            return self.SelectAdventurer(True)

        while(entry ==  "" or self.GetAdventurer(entry) is None):
            return self.SelectAdventurer(True)

        return self.GetAdventurer(entry)

    def GetItem(self, itemName):
        return self.bookCase.reserve[itemName]

    def GiveItem(self, itemName):
        '''give the item to the adventurer whom player will chose'''
        item = self.GetItem(itemName)

        speaker.Write(" =-= Item : " + str(item) + " =-=")

        adv = self.SelectAdventurer()
        adv.GiveItem(item)
        speaker.WriteInput(item.object + " gave to " + adv.getName() + " ! Tap ENTER to continue\n")

        return

    def GodGift(self):
        '''Give a lucky reward '''
        if self.godGift or tools.RollDice(1, 8) == 1:

            for adv in self.advGroup.values():
                adv.Heal(10)

            self.godGift = False

            return True
        return False




    



