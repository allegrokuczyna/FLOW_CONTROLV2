from sqlalchemy import Column, Integer, String, Float, Date, Boolean, DateTime, UniqueConstraint# dodaje Date
from app.db.database import Base
from datetime import datetime

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
    
    # To jest kluczowe dla funkcji "upsert" (żeby się nie duplikowało przy ponownym pobraniu)
    __table_args__ = (UniqueConstraint('login', 'work_date', name='uix_login_date'),)