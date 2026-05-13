from sqlalchemy import Column, Integer, String, Float, Date, Boolean, DateTime, UniqueConstraint, Text, func # dodaje Date
from app.db.database import Base
from datetime import datetime, date

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="WEB_USER") #sztywno web_user, 
    is_active = Column(Boolean, default=False)


class WorkExport(Base):
    __tablename__ = "work_exports"

    id = Column(Integer, primary_key=True, index=True)
    
    # Dane z WarehouseWorkHeaders (D365 OData)
    work_id = Column(String, unique=True, index=True)  # WarehouseWorkId
    order_num = Column(String, index=True)            # SourceOrderNumber
    zone2 = Column(String)                            # WHAAdditionalZone2
    item_qty = Column(Float)                          # WHASalesItemQty
    carrier_code = Column(String)                     # WHACarrierCode
    shipment_spec = Column(String)                    # WHAShipmentSpecId
    work_pool_id = Column(String)                     # WarehouseWorkPoolId
    
    # Dane z MerxWHASalesProcessingDates (Customowa encja)
    # zmieniam na Date 
    shipping_date = Column(Date, index=True)          # SalesWarehouseShippingDate




class WorkerPerformance(Base):
    __tablename__ = "worker_performances"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String, unique=True, index=True) 
    
    # Skille zmienione na Integer (0-6)
    forklift = Column(Integer, default=0)
    packing = Column(Integer, default=0)
    picking = Column(Integer, default=0)
    putaway = Column(Integer, default=0)
    receiving = Column(Integer, default=0)
    returns = Column(Integer, default=0)
    sorting = Column(Integer, default=0)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(50), index=True, nullable=False)
    work_date = Column(Date, index=True, nullable=False) 
    planned_shift = Column(String(50))
    is_present = Column(Boolean, default=False)
    group_prefix = Column(String, nullable=True) #prefikz z przypisaniem do dzialu O = Operacja.
    
    # To jest kluczowe dla funkcji "upsert" (żeby się nie duplikowało przy ponownym pobraniu)
    __table_args__ = (UniqueConstraint('login', 'work_date', name='uix_login_date'),)



class ActiveWork(Base):
    __tablename__ = "active_works"

    # Klucz główny
    id = Column(Integer, primary_key=True, index=True)
    
    # Podstawowe identyfikatory
    workid = Column(String, unique=True, index=True)
    ordernum = Column(String, index=True)
    shipmentid = Column(String, index=True)
    loadid = Column(String, index=True)
    waveid = Column(String, index=True)
    workpoolid = Column(String, index=True)
    
    # Statusy i typy
    workstatus = Column(String)  
    worktranstype = Column(String)
    
    # Ilości
    whasalesitemqty = Column(Float)
    whasalesitemcount = Column(Integer)
    whaworkitemsvolume = Column(Float)
    whaworkitemsweight = Column(Float)
    
    # Daty i Czas 
    whashippingdaterequested = Column(DateTime(timezone=True), nullable=True)
    whasaleswarehouseshippingdate = Column(DateTime(timezone=True), nullable=True)
    workcreateddatetime = Column(DateTime(timezone=True), nullable=True)
    workinprocessutcdatetime = Column(DateTime(timezone=True), nullable=True)
    workclosedutcdatetime = Column(DateTime(timezone=True), nullable=True)
    
    # Operacyjne
    lockeduser = Column(String, nullable=True) # UserId
    whaadditionalzone2 = Column(String, nullable=True) # Strefa
    whacarriercode = Column(String, nullable=True)
    whashipmentspecid = Column(String, nullable=True)
    targetlicenseplateid = Column(String, nullable=True)
    inventlocationid = Column(String)
    inventsiteid = Column(String)
    
    # Flagi (Boolean)
    workismultisku = Column(String) # D365 często zwraca "Yes"/"No"
    frozen = Column(String)
    
    # Pozostałe
    workpriority = Column(Integer)
    worktemplatecode = Column(String)
    containerid = Column(String)
    clusterid = Column(String)
    dataareaid = Column(String) # Firma (np. 'merx')
    
    # Meta-dane synchronizacji
    sinkmodifiedon = Column(DateTime(timezone=True), nullable=True)
    lastprocessedchange_datetime = Column(DateTime(timezone=True), nullable=True)



class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"

    id = Column(Integer, primary_key=True, index=True)
    worker_login = Column(String(50), nullable=False)
    shift = Column(String(5), nullable=False) 
    task = Column(String(50), nullable=False)
    assignment_date = Column(Date, default=date.today)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('worker_login', 'assignment_date', name='uq_worker_date'),)

#-------------odpowiedzi AI

class AiReportLog(Base):
    __tablename__ = "ai_report_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    workers_count = Column(Integer) # tutaj zwracam ilosc osob na zmianie
    report_text = Column(Text) #odpowiedx ai

class ForecastIntake(Base):
    __tablename__ = "forecast_intake"

    id = Column(Integer, primary_key=True, index=True)
    forecast_date = Column(Date, index=True)      
    hour_from = Column(DateTime(timezone=True), index=True) # Tu będzie np. 2026-05-13 08:00:00
    forecast_pcs = Column(Integer)
    actual_pcs = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint('forecast_date', 'hour_from', name='uix_forecast_date_hour'),)