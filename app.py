from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import chess
import json
from typing import Optional
from sqlalchemy.orm import Session
from hdc_engine import HDCEngine
from database import User, get_db

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
engine = HDCEngine()

room_boards = {}

class ConnectionManager:
    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = []
            room_boards[room_id] = chess.Board()
        self.rooms[room_id].append(websocket)
        await websocket.send_text(json.dumps({"status": "success", "fen": room_boards[room_id].fen()}))

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.rooms:
            self.rooms[room_id].remove(websocket)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
                if room_id in room_boards:
                    del room_boards[room_id]

    async def broadcast(self, message: str, room_id: str):
        if room_id in self.rooms:
            for connection in self.rooms[room_id]:
                await connection.send_text(message)

manager = ConnectionManager()

class MoveReq(BaseModel):
    source: str
    target: str
    mode: str
    room_id: str
    elo: int = 0

class UserCreate(BaseModel):
    username: str
    password: str

class GameOverReq(BaseModel):
    username: str
    result: str

def get_rank(elo):
    if elo < 500: return "NOVICE"
    elif elo < 1000: return "INTERMEDIATE"
    elif elo < 1500: return "MASTER"
    return "GRANDMASTER"

@app.get("/")
def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    new_user = User(username=user.username, password=user.password)
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@app.post("/login")
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username, User.password == user.password).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return {
        "message": "Login successful", 
        "username": db_user.username,
        "elo": db_user.elo_rating,
        "wins": db_user.wins,
        "rank": get_rank(db_user.elo_rating)
    }

@app.post("/reset")
async def reset_game(req: Optional[dict] = None):
    room_id = req.get('room_id', 'singleplayer') if req else 'singleplayer'
    room_boards[room_id] = chess.Board()
    await manager.broadcast(json.dumps({"status": "success", "fen": room_boards[room_id].fen()}), room_id)
    return {"status": "success"}

@app.post("/game_over")
def game_over(req: GameOverReq, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if user:
        if req.result == 'win':
            user.wins += 1
            user.elo_rating += 50
        db.commit()
        return {"status": "success", "elo": user.elo_rating, "wins": user.wins, "rank": get_rank(user.elo_rating)}
    return {"status": "error"}

@app.post("/move")
def make_move(req: MoveReq):
    board = room_boards.get(req.room_id)
    if not board:
        board = chess.Board()
        room_boards[req.room_id] = board
        
    move_uci = req.source + req.target
    try:
        piece = board.piece_at(chess.parse_square(req.source))
        if piece and piece.piece_type == chess.PAWN and chess.square_rank(chess.parse_square(req.target)) in [0, 7]:
            move_uci += 'q'
            
        chess_move = chess.Move.from_uci(move_uci)
        if chess_move in board.legal_moves:
            board.push(chess_move)
            if req.mode == 'ai' and not board.is_game_over():
                ai_move = engine.choose_move(board, req.elo)
                if ai_move:
                    board.push(ai_move)
            return {"status": "success", "fen": board.fen()}
    except Exception as e:
        print(f"Error aagaya: {e}")
    return {"status": "error"}

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            move_data = json.loads(data)
            board = room_boards.get(room_id)
            if not board: continue
            
            move_uci = move_data['source'] + move_data['target']
            try:
                piece = board.piece_at(chess.parse_square(move_data['source']))
                if piece and piece.piece_type == chess.PAWN and chess.square_rank(chess.parse_square(move_data['target'])) in [0, 7]:
                    move_uci += 'q'
                    
                chess_move = chess.Move.from_uci(move_uci)
                if chess_move in board.legal_moves:
                    board.push(chess_move)
                    await manager.broadcast(json.dumps({"status": "success", "fen": board.fen()}), room_id)
            except Exception:
                await websocket.send_text(json.dumps({"status": "invalid"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)