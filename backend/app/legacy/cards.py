class Cards:
    #Handles Card Creation
    def __init__(self,suit,rank,points,order):
        self.suit = suit
        self.rank = rank
        self.points = points
        self.order = order
    #Returns the card identity for a specific card object like Ace of Hearts
    def identity(self):
        return f"{self.rank} of {self.suit}"
    
    #Returns an entire pack of 28 cards
    @classmethod
    def packOf28(cls):
        pack = list([])
        suits = ["Hearts","Clubs","Diamonds","Spades"]
        ranks = ["Seven","Eight","Queen","King","Ten","Ace","Nine","Jack"]
        order = 0
        for suit in suits:
            for rank in ranks:
                point = 0
                order = ranks.index(rank)
                if rank == "Ten" or rank == "Ace":
                    point = 1
                if rank == "Nine":
                    point = 2
                if rank == "Jack":
                    point = 3

                card = cls(suit,rank,point,order)
                pack.append(card)

        return pack
    
    @classmethod
    def remaining(cls, cards):
        full_pack = cls.packOf28()
        cards_identities = set(card.identity() for card in cards)
        remaining_cards = [card for card in full_pack if card.identity() not in cards_identities]
        return remaining_cards
    
    # #Returns the same deck but the suit is only Hearts
    # @classmethod
    # def packOfSuit(cls):
        
    #     pack = list([])
    #     suits = ["Hearts","Hearts","Hearts","Hearts"]
    #     ranks = ["Seven","Eight","Queen","King","Ten","Ace","Nine","Jack"]
    #     order = 0
    #     for suit in suits:
    #         for rank in ranks:
    #             point = 0
    #             order = ranks.index(rank)
    #             if rank == "Ten" or rank == "Ace":
    #                 point = 1
    #             if rank == "Nine":
    #                 point = 2
    #             if rank == "Jack":
    #                 point = 3

    #             card = cls(suit,rank,point,order)
    #             pack.append(card)

    #     return pack



