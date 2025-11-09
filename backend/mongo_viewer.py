"""Simple web-based MongoDB viewer for AgentDog"""
from fastapi import FastAPI, APIRouter
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorClient
import os
from bson import ObjectId
import json
from datetime import datetime

app = FastAPI()
router = APIRouter()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "agentdog"

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

@router.get("/", response_class=HTMLResponse)
async def mongo_viewer():
    # Get all data
    users = await db.users.find({}, {"password_hash": 0}).to_list(100)
    runs = await db.runs.find({}).to_list(100)
    steps = await db.steps.find({}).to_list(100)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AgentDog MongoDB Viewer</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: 'Inter', -apple-system, sans-serif; 
                background: #f9fafb; 
                padding: 20px;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            h1 {{ 
                font-size: 28px; 
                font-weight: 700; 
                color: #0F172A; 
                margin-bottom: 8px;
            }}
            .subtitle {{ 
                color: #6B7280; 
                margin-bottom: 32px;
                font-size: 14px;
            }}
            .stats {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
                margin-bottom: 32px;
            }}
            .stat-card {{
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 20px;
            }}
            .stat-label {{
                font-size: 12px;
                font-weight: 600;
                color: #6B7280;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 8px;
            }}
            .stat-value {{
                font-size: 32px;
                font-weight: 700;
                color: #0F172A;
            }}
            .section {{
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 24px;
                margin-bottom: 24px;
            }}
            .section-title {{
                font-size: 16px;
                font-weight: 600;
                color: #0F172A;
                margin-bottom: 16px;
                padding-bottom: 12px;
                border-bottom: 1px solid #e5e7eb;
            }}
            .json-container {{
                background: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 16px;
                overflow-x: auto;
                max-height: 400px;
                overflow-y: auto;
            }}
            pre {{
                margin: 0;
                font-family: 'SF Mono', 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.6;
                color: #374151;
            }}
            .badge {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                margin-left: 8px;
            }}
            .badge-success {{ background: #DEF7EC; color: #03543F; }}
            .badge-error {{ background: #FDE8E8; color: #9B1C1C; }}
            .refresh-btn {{
                background: #2563EB;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                float: right;
            }}
            .refresh-btn:hover {{ background: #1D4ED8; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 16px;
            }}
            th, td {{
                text-align: left;
                padding: 12px;
                border-bottom: 1px solid #e5e7eb;
                font-size: 13px;
            }}
            th {{
                font-weight: 600;
                color: #6B7280;
                background: #f9fafb;
            }}
            td {{ color: #374151; }}
            .code {{ 
                font-family: 'SF Mono', monospace; 
                background: #f3f4f6; 
                padding: 2px 6px; 
                border-radius: 4px;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AgentDog MongoDB Viewer</h1>
            <p class="subtitle">Live view of your AgentDog database</p>
            
            <button class="refresh-btn" onclick="location.reload()">Refresh</button>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-label">Total Users</div>
                    <div class="stat-value">{len(users)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Runs</div>
                    <div class="stat-value">{len(runs)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Steps</div>
                    <div class="stat-value">{len(steps)}</div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">👥 Users ({len(users)})</div>
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Ingestion Key</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join([f'''
                        <tr>
                            <td>{user.get("name", "N/A")}</td>
                            <td>{user.get("email", "N/A")}</td>
                            <td><span class="code">{user.get("ingestion_key", "N/A")[:16]}...</span></td>
                            <td>{user.get("created_at", "N/A")}</td>
                        </tr>
                        ''' for user in users])}
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <div class="section-title">🏃 Runs ({len(runs)})</div>
                <table>
                    <thead>
                        <tr>
                            <th>Run ID</th>
                            <th>Status</th>
                            <th>Steps</th>
                            <th>Success</th>
                            <th>Failed</th>
                            <th>Integrity</th>
                            <th>Cost</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join([f'''
                        <tr>
                            <td><span class="code">{run.get("run_id", "N/A")}</span></td>
                            <td><span class="badge badge-{run.get("status", "")}">{run.get("status", "N/A").upper()}</span></td>
                            <td>{run.get("total_steps", 0)}</td>
                            <td>{run.get("success_steps", 0)}</td>
                            <td>{run.get("failed_steps", 0)}</td>
                            <td>{run.get("integrity_score", 0):.2f}</td>
                            <td>${run.get("cost", 0):.3f}</td>
                        </tr>
                        ''' for run in runs])}
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <div class="section-title">🔧 Steps ({len(steps)})</div>
                <div class="json-container">
                    <pre>{json.dumps(steps, indent=2, default=json_serial)}</pre>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">📊 Full Database Export (JSON)</div>
                <div class="json-container">
                    <pre>{json.dumps({{"users": users, "runs": runs, "steps": steps}}, indent=2, default=json_serial)}</pre>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

app.include_router(router, prefix="/mongo-viewer")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
