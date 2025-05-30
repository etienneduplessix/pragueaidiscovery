from fastapi import APIRouter, File, UploadFile, HTTPException
from sqlalchemy import text
from database import engine
from io import StringIO
import csv
import re

# Create a router instead of app
router = APIRouter()

# Upload CSV and insert into PostgreSQL
@router.post("/upload-csv/")
async def upload_csv(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        contents_str = contents.decode('utf-8')
        reader = csv.reader(StringIO(contents_str))
        
        headers = next(reader)
        headers = [re.sub(r"\W+", "_", h.strip().lower()) for h in headers]

        base_table_name = re.sub(r"\W+", "_", file.filename.lower())
        table_name = f"csv_{base_table_name}"

        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            {", ".join(f"{col} TEXT" for col in headers)}
        );
        """

        insert_sql = f"""
        INSERT INTO {table_name} ({", ".join(headers)})
        VALUES ({", ".join([f":{col}" for col in headers])})
        """

        inserted = 0
        with engine.begin() as conn:
            conn.execute(text(create_sql))
            for row in reader:
                if len(row) == len(headers):  # Ensure row has expected columns
                    row_dict = {col: val for col, val in zip(headers, row)}
                    conn.execute(text(insert_sql), row_dict)
                    inserted += 1

        return {"status": "success", "inserted": inserted, "table": table_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV upload failed: {str(e)}")
