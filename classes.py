import sqlalchemy
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy import Column, Date, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Racer(Base):
    __tablename__ = 'racers'
    id = Column(Integer, primary_key = True)
    name = Column(String)
    name_racing = Column(String)
    name_trueskill = Column(String)
    better_id = Column(Integer, ForeignKey('betters.id'))
    better = relationship("Better")

    def __repr__(self):
        return "<Racer(name='%s')>" % (
                             self.name)
    def __str__(self) :
        return "{} | {} | {}".format(self.name, self.name_racing, self.name_trueskill)

class Better(Base):
    __tablename__ = 'betters'
    id = Column(Integer, primary_key = True)
    name = Column(String)
    coin = Column(Integer)

class Bet(Base) :
    __tablename__ = 'bets'
    id = Column(Integer, primary_key = True)
    better_id = Column(Integer, ForeignKey('betters.id'))
    better = relationship("Better")
    race_id = Column(Integer, ForeignKey('races.id'))
    race = relationship("Race")
    winner_id = Column(Integer, ForeignKey('racers.id'))
    winner = relationship("Racer")
    coin_bet = Column(Integer)
    odd = Column(Float)
    def __str__(self) :
        return "Match #{} : {} vs {}, {} coins on {} at {} rate".format(self.race_id, self.race.racer1.name, self.race.racer2.name, self.coin_bet, self.winner.name, self.odd)

class Race (Base) :
    __tablename__ = 'races'
    id = Column(Integer, primary_key = True)
    racer1_id = Column(Integer, ForeignKey('racers.id'))
    racer1 = relationship("Racer", foreign_keys=[racer1_id])
    racer2_id = Column(Integer, ForeignKey('racers.id'))
    racer2 = relationship("Racer", foreign_keys=[racer2_id])
    odd1 = Column(Float)
    odd2 = Column(Float)
    ongoing = Column(Boolean)
    betsOn = Column(Boolean)
    format = Column(String) #seeded, diversity, unseeded, multiple
    tournament_id = Column(Integer, ForeignKey('tournaments.id'))
    tournament = relationship("Tournament")
    def __str__(self):
        return 'Match #{} : {} ({}) vs {} ({}) - {} ({} format)'.format(self.id, self.racer1.name,self.odd1, self.racer2.name, self.odd2,self.tournament.name, self.format)

class Tournament(Base):
    __tablename__ = 'tournaments'
    id = Column(Integer, primary_key = True)
    name = Column(String)
    challonge = Column(String)
    format = Column(String)
    def __str__(self):
        return "{}, format {}, link : {}".format(self.name, self.format, self.challonge)
