from sqlalchemy import Column, Integer, String, Float, Date, Boolean, DateTime, UniqueConstraint, Text, func, ForeignKey # dodaje Date
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
    full_name = Column(String(255), nullable=True)
    work_date = Column(Date, index=True, nullable=False) 
    planned_shift = Column(String(50))
    is_present = Column(Boolean, default=False)
    group_prefix = Column(String, nullable=True) #prefiks z przypisaniem do dzialu O = Operacja.
    gate = Column(Integer, nullable=True) #bramka, na której odbił się pracownik
    process = Column(String, nullable=True)
    # To jest kluczowe dla funkcji "upsert" (żeby się nie duplikowało przy ponownym pobraniu)
    __table_args__ = (UniqueConstraint('login', 'work_date', name='uix_login_date'),)

class WorkerSpecialTask(Base):
    __tablename__ = "worker_special_tasks"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String, index=True, unique=True) 
    process = Column(String, index=True)            
    task_name = Column(String)                      
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



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
    hour_from = Column(DateTime)
    forecast_pcs = Column(Integer)
    client_type = Column(String, index=True, default="1F")


#plan pracy magazynu

class ZoneConstraint(Base):
    __tablename__ = "zone_constraints"

    id = Column(Integer, primary_key=True, index=True)
    zone_name = Column(String, index=True) # usuwam unique true
    category = Column(String)  # Inbound / Outbound
    priority = Column(Integer)
    target_date = Column(Date, nullable=False, index=True)
    
    # Limity dla 3 zmian (Shift 1, 2, 3)
    s1_min = Column(Integer, nullable=True)
    s1_max = Column(Integer, nullable=True)
    s2_min = Column(Integer, nullable=True)
    s2_max = Column(Integer, nullable=True)
    s3_min = Column(Integer, nullable=True)
    s3_max = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint('zone_name', 'target_date', name='uq_zone_date'),
    )



    
    
#ilosc prac przenosnika mezaniny
class InboundMezzanineWorks(Base):
    __tablename__ = "inbound_mezzanine_works"

    id = Column(Integer, primary_key=True, index=True)
    work_pool_id = Column(String, unique=True, index=True)
    work_count = Column(Integer, default=0)
    item_qty = Column(Float, default=0.0)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


#ilosc sztuk w lokalizacjach 'techniczne przyjecia'
class InventoryQty(Base):
    __tablename__ = "inventory_qty"

    id = Column(Integer, primary_key=True, index=True)
    available_physical = Column(Integer, default=0)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)




class OutboundWork(Base):
    __tablename__ = "outbound_works"

    id = Column(Integer, primary_key=True, index=True)

    carrier = Column(String, index=True)
    work_pool_id = Column(String, index=True)
    work_qty = Column(Integer, default=0)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    
