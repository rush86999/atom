from sqlalchemy import create_engine, Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey, Text, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    email = Column(String)

class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    account_name = Column(String)
    account_type = Column(String)
    balance = Column(Numeric)
    user = relationship("User")

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    amount = Column(Numeric)
    description = Column(Text)
    date = Column(Date)
    category = Column(String)
    account = relationship("Account")

class Budget(Base):
    __tablename__ = 'budgets'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    name = Column(String)
    category = Column(String)
    amount = Column(Numeric)
    period_type = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    is_active = Column(Boolean)
    user = relationship("User")

class BudgetAlertSettings(Base):
    __tablename__ = 'budget_alert_settings'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    is_enabled = Column(Boolean, default=True)
    threshold = Column(Integer, default=90)
    user = relationship("User")
