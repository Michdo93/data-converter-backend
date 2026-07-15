import os
import io
import json
import yaml
import pandas as pd
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

MIME_TYPES = {
    'csv': 'text/csv',
    'json': 'application/json',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'yaml': 'text/yaml',
    'xml': 'application/xml'
}

def load_data_to_df(file_bytes, source_format):
    """Konvertiert die Eingabedaten dynamisch in einen Pandas DataFrame."""
    buffer = io.BytesIO(file_bytes)
    
    if source_format == 'csv':
        # Versucht automatisch, das richtige Trennzeichen (Komma oder Semikolon) zu finden
        try:
            return pd.read_csv(buffer, sep=None, engine='python')
        except Exception:
            buffer.seek(0)
            return pd.read_csv(buffer, sep=';')
            
    elif source_format == 'json':
        # Kann flache und leicht verschachtelte JSON-Arrays lesen
        try:
            return pd.read_json(buffer)
        except Exception:
            buffer.seek(0)
            data = json.loads(buffer.read().decode('utf-8'))
            if isinstance(data, dict):
                data = [data] # In Liste packen, falls es ein einzelnes Objekt war
            return pd.json_normalize(data)
            
    elif source_format == 'xlsx':
        return pd.read_excel(buffer)
        
    elif source_format == 'yaml':
        data = yaml.safe_load(buffer.read().decode('utf-8'))
        if isinstance(data, dict):
            data = [data]
        return pd.json_normalize(data)
        
    elif source_format == 'xml':
        return pd.read_xml(buffer)
        
    else:
        raise ValueError(f"Ungültiges Quellformat: {source_format}")

@app.route('/convert', methods=['POST'])
def convert_data():
    if 'file' not in request.files:
        return jsonify({"error": "Keine Datei hochgeladen"}), 400
    
    file = request.files['file']
    target_format = request.form.get('target_format', '').lower().strip()
    
    if file.filename == '' or not target_format:
        return jsonify({"error": "Ungültige Parameter"}), 400

    filename, file_extension = os.path.splitext(file.filename)
    source_format = file_extension.lower().replace('.', '')
    
    # Ausnahmen für Dateiendungen korrigieren
    if source_format == 'yml': source_format = 'yaml'
    if source_format == 'xls': source_format = 'xlsx'

    if source_format == target_format:
        return jsonify({"error": "Quell- und Zielformat sind identisch."}), 400

    try:
        file_bytes = file.read()
        
        # 1. Daten einlesen
        df = load_data_to_df(file_bytes, source_format)
        
        # 2. In Zielformat konvertieren
        output_buffer = io.BytesIO()
        
        if target_format == 'csv':
            df.to_csv(output_buffer, index=False, encoding='utf-8')
            
        elif target_format == 'json':
            # Schön formatiertes JSON exportieren
            json_str = df.to_json(orient='records', indent=4, force_ascii=False)
            output_buffer.write(json_str.encode('utf-8'))
            
        elif target_format == 'xlsx':
            with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Daten')
                
        elif target_format == 'yaml':
            # DataFrame in Dictionary-Liste umwandeln und als YAML dumpen
            data_dict = df.to_dict(orient='records')
            yaml_str = yaml.dump(data_dict, allow_unicode=True, sort_keys=False)
            output_buffer.write(yaml_str.encode('utf-8'))
            
        elif target_format == 'xml':
            df.to_xml(output_buffer, index=False, parser='etree', encoding='utf-8')
            
        else:
            return jsonify({"error": f"Zielformat {target_format} nicht unterstützt."}), 400

        output_buffer.seek(0)
        mime = MIME_TYPES.get(target_format, 'application/octet-stream')

        return send_file(
            output_buffer,
            mimetype=mime,
            as_attachment=True,
            download_name=f"{filename}.{target_format}"
        )

    except Exception as e:
        return jsonify({"error": f"Fehler bei der Konvertierung: {str(e)}. Bitte überprüfe die Struktur deiner Datei."}), 500

if __name__ == '__main__':
    app.run(port=8080)
