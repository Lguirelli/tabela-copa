
RUN SYSTEM:

1. ETL:
   python ingestion/main.py

2. MODEL API:
   uvicorn api.app:app --reload

3. DASHBOARD:
   open dashboard/index.html

FLOW:
ETL -> Warehouse -> Model -> API -> Dashboard
