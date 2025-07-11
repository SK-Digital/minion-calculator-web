from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import re
import requests as pyrequests
from io import BytesIO

app = Flask(__name__)

# Load minion and upgrade data
DATA_PATH = os.path.join(os.path.dirname(__file__), 'hypixel_minion_data.json')
with open(DATA_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)
    MINIONS = data.get('minions', {})
    UPGRADES = data.get('upgrades', {})

# Helper to parse shorthand numbers
ROMAN_TO_INT = {
    'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11,
    'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15, 'XVI': 16, 'XVII': 17, 'XVIII': 18, 'XIX': 19, 'XX': 20
}
def parse_shorthand_number(s):
    if isinstance(s, (int, float)):
        return int(s)
    s = str(s).replace(',', '').strip().lower()
    match = re.fullmatch(r'([\d,.]+)([kmb]?)', s)
    if not match:
        raise ValueError(f"Invalid number format: {s}")
    num, suffix = match.groups()
    try:
        num = float(num)
    except ValueError:
        raise ValueError(f"Invalid number: {num}")
    if suffix == 'k':
        num *= 1_000
    elif suffix == 'm':
        num *= 1_000_000
    elif suffix == 'b':
        num *= 1_000_000_000
    return int(num)

def calculate_output(minion, tier, num_minions, upgrades, hours, minion_data, upgrade_data):
    minion_info = minion_data.get(minion)
    if not minion_info:
        raise ValueError(f"No data for {minion}")
    row = next((r for r in minion_info['production'] if r['tier'] == tier), None)
    if not row:
        raise ValueError(f"No data for {minion} tier {tier}")
    base_actions_per_hour = row['actions_per_hour']
    base_output_per_action = row['output_per_action']
    speed_multiplier = 1.0
    for upg in upgrades:
        upg_info = upgrade_data.get(upg)
        if upg_info and isinstance(upg_info.get('multiplier'), (int, float)):
            speed_multiplier *= upg_info['multiplier']
    total_actions = base_actions_per_hour * speed_multiplier * hours * num_minions
    total_output = total_actions * base_output_per_action
    return total_output, speed_multiplier

@app.route('/')
def index():
    return render_template('index.html', minions=MINIONS, upgrades=UPGRADES)

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    sets = data.get('sets')
    if not sets:
        # fallback for single set
        sets = [{
            'minion': data.get('minion'),
            'tier': data.get('tier'),
            'amount': data.get('amount', 1),
            'upgrades': data.get('upgrades', []),
            'hours': data.get('hours', 24)
        }]
    results = []
    total_output = 0
    try:
        for s in sets:
            minion = s.get('minion')
            tier = s.get('tier')
            num_minions = int(s.get('amount', 1))
            upgrades = s.get('upgrades', [])
            hours = float(s.get('hours', 24))
            total, sm = calculate_output(minion, tier, num_minions, upgrades, hours, MINIONS, UPGRADES)
            resource = MINIONS[minion]['resource']
            results.append({
                'minion': minion,
                'output': int(total),
                'resource': resource,
                'speed_multiplier': round(sm, 2)
            })
            total_output += total
        return jsonify({'success': True, 'results': results, 'total_output': int(total_output)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/calculate_hours', methods=['POST'])
def calculate_hours():
    data = request.json
    sets = data.get('sets')
    amount_to_collect_raw = data.get('amount_to_collect', 0)
    try:
        amount_to_collect = parse_shorthand_number(amount_to_collect_raw)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Invalid amount to collect: {e}'})
    if not sets:
        sets = [{
            'minion': data.get('minion'),
            'tier': data.get('tier'),
            'amount': data.get('amount', 1),
            'upgrades': data.get('upgrades', []),
            'hours': data.get('hours', 24)
        }]
    results = []
    total_hours_needed = 0
    try:
        for s in sets:
            minion = s.get('minion')
            tier = s.get('tier')
            num_minions = int(s.get('amount', 1))
            upgrades = s.get('upgrades', [])
            minion_info = MINIONS.get(minion)
            row = next((r for r in minion_info['production'] if r['tier'] == tier), None)
            base_actions_per_hour = row['actions_per_hour']
            base_output_per_action = row['output_per_action']
            speed_multiplier = 1.0
            for upg in upgrades:
                upg_info = UPGRADES.get(upg)
                if upg_info and isinstance(upg_info.get('multiplier'), (int, float)):
                    speed_multiplier *= upg_info['multiplier']
            output_per_hour = base_actions_per_hour * speed_multiplier * base_output_per_action * num_minions
            resource = minion_info['resource']
            if output_per_hour <= 0:
                results.append({'minion': minion, 'error': 'Output per hour is zero or negative.'})
                continue
            hours_needed = amount_to_collect / output_per_hour if output_per_hour else 0
            results.append({
                'minion': minion,
                'output_per_hour': int(output_per_hour),
                'resource': resource,
                'hours_needed': round(hours_needed, 2),
                'speed_multiplier': round(speed_multiplier, 2)
            })
            total_hours_needed += hours_needed
        return jsonify({'success': True, 'results': results, 'total_hours_needed': round(total_hours_needed, 2)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/img_proxy')
def img_proxy():
    url = request.args.get('url')
    if not url or not url.startswith('http'):
        return send_file('static/no-image.png', mimetype='image/png')
    try:
        resp = pyrequests.get(url, timeout=8)
        resp.raise_for_status()
        content_type = resp.headers.get('Content-Type', 'image/png')
        return send_file(BytesIO(resp.content), mimetype=content_type)
    except Exception:
        return send_file('static/no-image.png', mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True) 