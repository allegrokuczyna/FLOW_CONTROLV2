from sqlalchemy import Column, Integer, String, Float, Date, Boolean, DateTime, UniqueConstraint# dodaje Date
from app.db.database import Base
from datetime import datetime

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
    
    # Procenty zamienione na float
    forklift = Column(Float, default=0.0)
    packing = Column(Float, default=0.0)
    picking = Column(Float, default=0.0)
    putaway = Column(Float, default=0.0)
    receiving = Column(Float, default=0.0)
    returns = Column(Float, default=0.0)
    sorting = Column(Float, default=0.0)
    
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