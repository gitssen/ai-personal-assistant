import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const LOG_DIR = path.join(process.cwd(), 'logs');
const LOG_FILE = path.join(LOG_DIR, 'frontend.log');
const MAX_BACKUPS = 5;
const MAX_SIZE = 5 * 1024 * 1024; // 5MB

function rotateLogs() {
  if (!fs.existsSync(LOG_FILE)) return;
  
  const stats = fs.statSync(LOG_FILE);
  if (stats.size < MAX_SIZE) return;

  // Rotate backups
  for (let i = MAX_BACKUPS - 1; i >= 1; i--) {
    const oldPath = `${LOG_FILE}.${i}`;
    const newPath = `${LOG_FILE}.${i + 1}`;
    if (fs.existsSync(oldPath)) {
      fs.renameSync(oldPath, newPath);
    }
  }
  
  // Move current to .1
  fs.renameSync(LOG_FILE, `${LOG_FILE}.1`);
}

export async function POST(req: NextRequest) {
  try {
    const { level, message, data } = await req.json();
    
    if (!fs.existsSync(LOG_DIR)) {
      fs.mkdirSync(LOG_DIR, { recursive: true });
    }

    rotateLogs();

    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] [${level.toUpperCase()}] ${message} ${data ? JSON.stringify(data) : ''}\n`;
    
    fs.appendFileSync(LOG_FILE, logEntry);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Failed to log:', error);
    return NextResponse.json({ success: false }, { status: 500 });
  }
}
