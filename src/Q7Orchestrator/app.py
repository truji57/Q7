"""
Q7 Dashboard - Flask App
Sirve la interfaz web y WebSocket para monitorizacion en tiempo real.
Ejecutar: python app.py
"""

import os
import sys
import json
import threading
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

sys.path.insert(0, os.path.dirname(__file__))
from orchestrator import Orchestrator
from signal_watcher import SignalWatcher

app = Flask(__name__, template_folder='../Q7Dashboard/templates', static_folder='../Q7Dashboard/static')
app.config['SECRET_KEY'] = 'q7-dashboard-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

orchestrator: Orchestrator = None
watcher: SignalWatcher = None
broadcast_thread: threading.Thread = None
broadcast_running: bool = True


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/state')
def api_state():
    if orchestrator:
        return jsonify(orchestrator.get_dashboard_state())
    return jsonify({'error': 'Orchestrator not initialized'}), 500


@app.route('/api/command', methods=['POST'])
def api_command():
    cmd = request.json.get('command', '').upper()
    if not orchestrator:
        return jsonify({'error': 'Not initialized'}), 500

    result = {}
    if cmd == 'START':
        orchestrator.start()
        result = {'status': 'started'}
    elif cmd == 'STOP':
        orchestrator.stop()
        result = {'status': 'stopped'}
    elif cmd == 'PAUSE':
        paused = orchestrator.pause()
        result = {'status': 'paused' if paused else 'resumed'}
    elif cmd == 'SKIP':
        account_id = orchestrator.skip_account()
        result = {'status': 'skipped', 'new_account_id': account_id}
    elif cmd == 'ROTATE':
        orchestrator.rotate_account()
        result = {'status': 'rotated'}

    return jsonify(result)


@app.route('/api/report_trade', methods=['POST'])
def api_report_trade():
    pnl = request.json.get('pnl', 0)
    if orchestrator:
        orchestrator.report_trade_result(float(pnl))
    return jsonify({'status': 'ok'})


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


@socketio.on('connect')
def on_connect():
    emit('connected', {'status': 'ok'})


@socketio.on('get_state')
def on_get_state():
    if orchestrator:
        emit('state_update', orchestrator.get_dashboard_state())


def broadcast_loop():
    """Envia estado del orchestrator al dashboard cada 1s via WebSocket"""
    while broadcast_running:
        try:
            if orchestrator:
                state = orchestrator.get_dashboard_state()
                socketio.emit('state_update', state)
        except Exception as e:
            print(f"Broadcast error: {e}")
        socketio.sleep(1)


def init_orchestrator(config_path: str = 'config.json'):
    global orchestrator, watcher
    orchestrator = Orchestrator(config_path)
    watcher = SignalWatcher(orchestrator.signals_path, orchestrator)

    watcher_thread = threading.Thread(target=watcher.start, daemon=True)
    watcher_thread.start()

    broadcast = threading.Thread(target=broadcast_loop, daemon=True)
    broadcast.start()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Q7 Orchestrator + Dashboard')
    parser.add_argument('--config', default='config.json', help='Path to config.json')
    parser.add_argument('--host', default='127.0.0.1', help='Bind host')
    parser.add_argument('--port', type=int, default=5000, help='Bind port')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    args = parser.parse_args()

    config_dir = os.path.dirname(os.path.abspath(args.config))
    if config_dir:
        os.chdir(config_dir)

    init_orchestrator(args.config)

    print(f"\n{'='*60}")
    print(f"  Q7 Orchestrator + Dashboard")
    print(f"  http://{args.host}:{args.port}")
    print(f"{'='*60}\n")

    socketio.run(app, host=args.host, port=args.port, debug=args.debug, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
