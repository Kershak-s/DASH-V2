import random
import sqlite3
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

DATABASE = 'database.db'  # Ajusta según tu proyecto

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Renderiza el dashboard."""
    return render_template('dashboard.html')

@app.route('/get-plants', methods=['GET'])
def get_plants():
    """Devuelve la lista de plantas únicas de la tabla ccw."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT plant FROM ccw WHERE plant IS NOT NULL AND plant <> ''")
    rows = cursor.fetchall()
    conn.close()
    plants = [row['plant'] for row in rows]
    return jsonify(plants)

@app.route('/plant-lines', methods=['POST'])
def plant_lines():
    """Dada una planta, retorna las líneas disponibles (tabla ccw)."""
    data = request.get_json()
    plant = data.get('plant')
    if not plant:
        return jsonify([])
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT DISTINCT line
        FROM ccw
        WHERE plant = ? AND line IS NOT NULL AND line <> ''
    """
    cursor.execute(query, (plant,))
    rows = cursor.fetchall()
    conn.close()
    lines = [row['line'] for row in rows]
    return jsonify(lines)

@app.route('/equipment-by-filter', methods=['POST'])
def equipment_by_filter():
    """Dado planta y línea, retorna los equipos (eq) de ccw."""
    data = request.get_json()
    plant = data.get('plant')
    line = data.get('line')
    conn = get_db_connection()
    cursor = conn.cursor()
    base_query = "SELECT DISTINCT eq FROM ccw WHERE eq IS NOT NULL AND eq <> ''"
    conditions = []
    params = []
    if plant:
        conditions.append("plant = ?")
        params.append(plant)
    if line:
        conditions.append("line = ?")
        params.append(line)
    if conditions:
        base_query += " AND " + " AND ".join(conditions)
    cursor.execute(base_query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    equipment_list = [row['eq'] for row in rows]
    return jsonify(equipment_list)

@app.route('/available-dates', methods=['GET'])
def available_dates():
    """Retorna el rango de fechas disponibles de ccw y tsc."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Ajusta las columnas de fecha según tus tablas
    cursor.execute("SELECT MIN(date_start) as min_ccw, MAX(date_end) as max_ccw FROM ccw")
    ccw_row = cursor.fetchone()
    cursor.execute("SELECT MIN(date_start) as min_tsc, MAX(date_end) as max_tsc FROM tsc")
    tsc_row = cursor.fetchone()
    conn.close()
    min_candidates = []
    max_candidates = []
    if ccw_row['min_ccw']:
        min_candidates.append(ccw_row['min_ccw'])
    if tsc_row['min_tsc']:
        min_candidates.append(tsc_row['min_tsc'])
    if ccw_row['max_ccw']:
        max_candidates.append(ccw_row['max_ccw'])
    if tsc_row['max_tsc']:
        max_candidates.append(tsc_row['max_tsc'])
    if not min_candidates or not max_candidates:
        return jsonify({})
    overall_min = min(min_candidates)
    overall_max = max(max_candidates)
    return jsonify({"min_date": overall_min, "max_date": overall_max})

@app.route('/equipment-summary', methods=['GET'])
def equipment_summary():
    """
    Retorna un resumen fijo de equipos instalados vs. cargados (datos de ejemplo).
    Ajusta estos datos a tu conveniencia o conéctalos a tu BD si lo deseas.
    """
    data = [
        {"plant": "FUNZA",     "installed": 4,  "loaded": 4},
        {"plant": "ORIENTE",   "installed": 20, "loaded": 20},
        {"plant": "CURITIBA",  "installed": 24, "loaded": 24},
        {"plant": "OBREGON",   "installed": 16, "loaded": 16},
        {"plant": "GUATEMALA", "installed": 16, "loaded": 10},
        {"plant": "ORIZABA",   "installed": 31, "loaded": 27},
        {"plant": "RECIFE",    "installed": 10, "loaded": 0}
    ]
    summary = []
    for item in data:
        installed = item["installed"]
        loaded = item["loaded"]
        percentage = (loaded / installed * 100) if installed > 0 else 0
        if percentage >= 90:
            status = "Cargados"
        elif percentage >= 50:
            status = "Parcial"
        else:
            status = "No cargados"
        summary.append({
            "plant": item["plant"],
            "installed": installed,
            "loaded": loaded,
            "percentage": percentage,
            "status": status
        })
    return jsonify(summary)

@app.route('/plant-ranking', methods=['GET'])
def plant_ranking():
    """
    Ranking de plantas que se mostrará en la tabla "Ranking de Plantas (por Sobrepeso)".
    Para cada planta se calculan:
      - Bolsas Buenas (TSC): suma de good_bags en tsc.
      - Bolsas Buenas (CCW): suma de descargas_buenas en ccw.
      - Sobrepeso (bolsas): sumatoria de sobre_peso en ccw (o la métrica que uses).
      - Eficiencia (%): promedio de las eficiencias (ccw, atlas y tsc) (solo valores > 0).
      - Des Estandar: promedio de des_estandar en ccw.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
        SELECT 
            p.plant,
            (SELECT SUM(tsc.good_bags) FROM tsc WHERE tsc.plant = p.plant) AS total_good,
            (SELECT SUM(ccw.descargas_buenas) FROM ccw WHERE ccw.plant = p.plant) AS total_good_ccw,
            (SELECT SUM(ccw.sobre_peso) FROM ccw WHERE ccw.plant = p.plant) AS total_overweight,
            (SELECT AVG(ccw.des_estandar) FROM ccw WHERE ccw.plant = p.plant) AS avg_desestandar,
            (SELECT AVG(ccw.eficiencia_ccw) FROM ccw WHERE ccw.plant = p.plant) AS avg_ccw,
            (SELECT AVG(ccw.eficiencia_atlas) FROM ccw WHERE ccw.plant = p.plant) AS avg_atlas,
            (SELECT AVG(tsc.eficiencia_tsc) FROM tsc WHERE tsc.plant = p.plant) AS avg_tsc
        FROM (
            SELECT DISTINCT plant 
            FROM ccw 
            WHERE plant IS NOT NULL AND plant <> ''
            UNION 
            SELECT DISTINCT plant 
            FROM tsc 
            WHERE plant IS NOT NULL AND plant <> ''
        ) p
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        ranking = []
        for row in rows:
            plant = row['plant']
            total_good = row['total_good'] if row['total_good'] is not None else 0
            total_good_ccw = row['total_good_ccw'] if row['total_good_ccw'] is not None else 0
            overweight_total = row['total_overweight'] if row['total_overweight'] is not None else 0
            avg_desestandar = row['avg_desestandar'] if row['avg_desestandar'] is not None else 0
            
            avg_ccw = row['avg_ccw'] if row['avg_ccw'] is not None else 0
            avg_atlas = row['avg_atlas'] if row['avg_atlas'] is not None else 0
            avg_tsc = row['avg_tsc'] if row['avg_tsc'] is not None else 0
            
            # Promediar solo valores positivos
            eff_list = []
            if avg_ccw > 0:
                eff_list.append(avg_ccw)
            if avg_atlas > 0:
                eff_list.append(avg_atlas)
            if avg_tsc > 0:
                eff_list.append(avg_tsc)
            overall_eff = sum(eff_list) / len(eff_list) if eff_list else 0
            
            ranking.append({
                "plant": plant,
                "total_good": total_good,
                "total_good_ccw": total_good_ccw,
                "overweight_total": overweight_total,
                "overall_efficiency": overall_eff,
                "avg_desestandar": avg_desestandar
            })
        
        # Ordenar por eficiencia promedio de mayor a menor
        ranking = sorted(ranking, key=lambda x: x["overall_efficiency"], reverse=True)
        conn.close()
        return jsonify(ranking)
    except Exception as e:
        print("Error en /plant-ranking:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/pareto-defects', methods=['POST'])
def pareto_defects():
    """
    Retorna el análisis de Pareto de los defectos (bolsas defectuosas) a partir de tsc.
    Calcula la suma de leak_bags, flat_bags, double_bags y thick_bags y sus porcentajes.
    """
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    plant = data.get('plant')
    line = data.get('line')
    equipment = data.get('equipment')
    
    where_tsc = []
    params_tsc = []
    if start_date:
        where_tsc.append("date_start >= ?")
        params_tsc.append(start_date)
    if end_date:
        where_tsc.append("date_end <= ?")
        params_tsc.append(end_date)
    if plant:
        where_tsc.append("plant = ?")
        params_tsc.append(plant)
    if line:
        where_tsc.append("line = ?")
        params_tsc.append(line)
    if equipment:
        where_tsc.append("eq = ?")
        params_tsc.append(equipment)
    where_sql = ""
    if where_tsc:
        where_sql = "WHERE " + " AND ".join(where_tsc)
    
    query = f"""
       SELECT
           SUM(leak_bags) as leak_bags,
           SUM(flat_bags) as flat_bags,
           SUM(double_bags) as double_bags,
           SUM(thick_bags) as thick_bags
       FROM tsc
       {where_sql}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params_tsc)
    row = cursor.fetchone()
    conn.close()
    
    leak = row["leak_bags"] or 0
    flat = row["flat_bags"] or 0
    double = row["double_bags"] or 0
    thick = row["thick_bags"] or 0
    total_defects = leak + flat + double + thick
    if total_defects > 0:
        leak_pct = (leak / total_defects) * 100
        flat_pct = (flat / total_defects) * 100
        double_pct = (double / total_defects) * 100
        thick_pct = (thick / total_defects) * 100
    else:
        leak_pct = flat_pct = double_pct = thick_pct = 0
    return jsonify({
        "leak_bags": leak,
        "flat_bags": flat,
        "double_bags": double,
        "thick_bags": thick,
        "total": total_defects,
        "leak_pct": leak_pct,
        "flat_pct": flat_pct,
        "double_pct": double_pct,
        "thick_pct": thick_pct
    })

@app.route('/dashboard-data', methods=['POST'])
def dashboard_data():
    """
    Endpoint principal que retorna:
      - KPIs generales: Eficiencia General, Tasa de Desperdicio, Bolsas Buenas, Bolsas Teóricas.
      - Eficiencia por equipo: CCW, ATLAS, TSC.
      - Eficiencia Manual vs. Automática.
      - Bolsas defectuosas.
      - Análisis de Sobrepeso.
    """
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    plant = data.get('plant')
    line = data.get('line')
    equipment = data.get('equipment')
    
    # Filtros para ccw
    where_ccw = []
    params_ccw = []
    if start_date:
        where_ccw.append("ccw.date_start >= ?")
        params_ccw.append(start_date)
    if end_date:
        where_ccw.append("ccw.date_end <= ?")
        params_ccw.append(end_date)
    if plant:
        where_ccw.append("ccw.plant = ?")
        params_ccw.append(plant)
    if line:
        where_ccw.append("ccw.line = ?")
        params_ccw.append(line)
    if equipment:
        where_ccw.append("ccw.eq = ?")
        params_ccw.append(equipment)
    where_sql_ccw = ""
    if where_ccw:
        where_sql_ccw = "WHERE " + " AND ".join(where_ccw)
    
    # Query para ccw (KPIs generales y eficiencia de CCW, ATLAS, des_estandar)
    query_ccw = f"""
        SELECT
           AVG(ccw.eficiencia_ccw)   AS avg_ccw_eff,
           AVG(ccw.eficiencia_atlas) AS avg_atlas_eff,
           AVG(ccw.des_estandar)     AS avg_desestandar
        FROM ccw
        {where_sql_ccw}
    """
    
    # Filtros para tsc
    where_tsc = []
    params_tsc = []
    if start_date:
        where_tsc.append("tsc.date_start >= ?")
        params_tsc.append(start_date)
    if end_date:
        where_tsc.append("tsc.date_end <= ?")
        params_tsc.append(end_date)
    if plant:
        where_tsc.append("tsc.plant = ?")
        params_tsc.append(plant)
    if line:
        where_tsc.append("tsc.line = ?")
        params_tsc.append(line)
    if equipment:
        where_tsc.append("tsc.eq = ?")
        params_tsc.append(equipment)
    where_sql_tsc = ""
    if where_tsc:
        where_sql_tsc = "WHERE " + " AND ".join(where_tsc)
    
    # Query para tsc (eficiencia_tsc, good_bags, defectos)
    query_tsc = f"""
        SELECT
           AVG(tsc.eficiencia_tsc)     AS avg_tsc_eff,
           SUM(tsc.good_bags)          AS sum_good_bags,
           SUM(tsc.leak_bags)          AS sum_leak_bags,
           SUM(tsc.flat_bags)          AS sum_flat_bags,
           SUM(tsc.double_bags)        AS sum_double_bags,
           SUM(tsc.thick_bags)         AS sum_thick_bags
        FROM tsc
        {where_sql_tsc}
    """
    
    # Suponiendo que existe una tabla tsc_daily con total_bags teóricas
    # Si no la usas, puedes omitir esta parte
    where_tscd = []
    params_tscd = []
    if start_date:
        where_tscd.append("td.date >= ?")
        params_tscd.append(start_date)
    if end_date:
        where_tscd.append("td.date <= ?")
        params_tscd.append(end_date)
    if plant:
        where_tscd.append("tsc.plant = ?")
        params_tscd.append(plant)
    if line:
        where_tscd.append("tsc.line = ?")
        params_tscd.append(line)
    if equipment:
        where_tscd.append("tsc.eq = ?")
        params_tscd.append(equipment)
    where_sql_tscd = ""
    if where_tscd:
        where_sql_tscd = "WHERE " + " AND ".join(where_tscd)
    
    query_tsc_daily = f"""
        SELECT SUM(td.total_bags) AS sum_total_bags
        FROM tsc_daily td
        JOIN tsc ON td.tsc_id = tsc.id
        {where_sql_tscd}
    """
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # Ejecutar query_ccw
    cursor.execute(query_ccw, params_ccw)
    row_ccw = cursor.fetchone()
    # Ejecutar query_tsc
    cursor.execute(query_tsc, params_tsc)
    row_tsc = cursor.fetchone()
    # Ejecutar query_tsc_daily para bolsas teóricas
    cursor.execute(query_tsc_daily, params_tscd)
    row_tsc_daily = cursor.fetchone()
    
    # KPIs generales
    avg_ccw_eff = row_ccw['avg_ccw_eff'] or 0
    avg_atlas_eff = row_ccw['avg_atlas_eff'] or 0
    avg_tsc_eff = row_tsc['avg_tsc_eff'] or 0
    effs = []
    if avg_ccw_eff > 0: effs.append(avg_ccw_eff)
    if avg_atlas_eff > 0: effs.append(avg_atlas_eff)
    if avg_tsc_eff > 0: effs.append(avg_tsc_eff)
    overall_eff = sum(effs)/len(effs) if effs else 0
    
    avg_desestandar = row_ccw['avg_desestandar'] or 0
    sum_good_bags = row_tsc['sum_good_bags'] or 0
    sum_total_bags = row_tsc_daily['sum_total_bags'] if row_tsc_daily and row_tsc_daily['sum_total_bags'] else 0
    
    # Eficiencia Manual (ccw sin tsc)
    query_manual = f"""
        SELECT
          AVG(ccw.eficiencia_ccw)   AS avg_ccw,
          AVG(ccw.eficiencia_atlas) AS avg_atlas
        FROM ccw
        LEFT JOIN tsc ON ccw.id = tsc.ccw_id
    """
    cond_manual = list(where_ccw)
    cond_manual.append("tsc.id IS NULL")  # Solo registros sin TSC asociado
    where_sql_manual = ""
    if cond_manual:
        where_sql_manual = "WHERE " + " AND ".join(cond_manual)
    query_manual += " " + where_sql_manual
    cursor.execute(query_manual, params_ccw)
    row_manual = cursor.fetchone()
    manual_ccw = row_manual['avg_ccw'] or 0
    manual_atlas = row_manual['avg_atlas'] or 0
    man_effs = []
    if manual_ccw > 0: man_effs.append(manual_ccw)
    if manual_atlas > 0: man_effs.append(manual_atlas)
    manual_efficiency = sum(man_effs)/len(man_effs) if man_effs else 0
    
    # Eficiencia Automática (ccw con tsc)
    query_auto = f"""
        SELECT
          AVG(ccw.eficiencia_ccw)   AS avg_ccw,
          AVG(ccw.eficiencia_atlas) AS avg_atlas,
          AVG(tsc.eficiencia_tsc)   AS avg_tsc
        FROM ccw
        JOIN tsc ON ccw.id = tsc.ccw_id
    """
    where_sql_auto = ""
    if where_ccw:
        where_sql_auto = "WHERE " + " AND ".join(where_ccw)
    query_auto += " " + where_sql_auto
    cursor.execute(query_auto, params_ccw)
    row_auto = cursor.fetchone()
    auto_ccw = row_auto['avg_ccw'] or 0
    auto_atlas = row_auto['avg_atlas'] or 0
    auto_tsc = row_auto['avg_tsc'] or 0
    aut_effs = []
    if auto_ccw > 0: aut_effs.append(auto_ccw)
    if auto_atlas > 0: aut_effs.append(auto_atlas)
    if auto_tsc > 0: aut_effs.append(auto_tsc)
    automatic_efficiency = sum(aut_effs)/len(aut_effs) if aut_effs else 0
    
    # Bolsas defectuosas
    sum_leak_bags = row_tsc['sum_leak_bags'] or 0
    sum_flat_bags = row_tsc['sum_flat_bags'] or 0
    sum_double_bags = row_tsc['sum_double_bags'] or 0
    sum_thick_bags = row_tsc['sum_thick_bags'] or 0
    
    # Análisis de Sobrepeso (ejemplo: good_bags * 0.1 g). Ajusta según tu lógica real
    overweight_grams = sum_good_bags * 0.1
    
    conn.close()
    
    response = {
        "metrics": {
            "overall_efficiency": overall_eff,
            "waste_rate": avg_desestandar,
            "good_bags": sum_good_bags,
            "theoretical_bags": sum_total_bags,
            "ccw_efficiency": avg_ccw_eff,
            "atlas_efficiency": avg_atlas_eff,
            "tsc_efficiency": avg_tsc_eff,
            "manual_efficiency": manual_efficiency,
            "automatic_efficiency": automatic_efficiency,
            "leak_bags": sum_leak_bags,
            "flat_bags": sum_flat_bags,
            "double_bags": sum_double_bags,
            "thick_bags": sum_thick_bags,
            "overweight_grams": overweight_grams
        },
        "comparison": {},
        "trends": {},
        "forecasts": {},
        "weight_analysis": {},
        "plant_comparison": {}
    }
    return jsonify(response)

# Nuevo endpoint: /dme-failures
@app.route('/dme-failures', methods=['POST'])
def dme_failures():
    """
    Retorna un Top 3 de fallas “jugando” con 10 posibles nombres.
    Si se reciben filtros (plant, line, etc.), puedes personalizar la lógica.
    """
    data = request.get_json()
    plant = data.get('plant', '')
    line = data.get('line', '')

    # Lista base de 10 fallas
    base_errors = [
        "ZERO ERROR",
        "ZERO ERROR",   # Repetida, si deseas
        "SPAN ERROR",
        "WH ERROR",
        "PH ERROR",
        "BH ERROR",
        "RS ERROR",
        "DTH ERROR",
        "TH ERROR",
        "PIECE WEIGHT ERROR"
    ]

    # Ejemplo: si hay un filtro de planta, podrías modificar la lista o los conteos
    # if plant == "FUNZA":
    #     base_errors = ["RS ERROR", "ZERO ERROR", "SPAN ERROR", ...]
    # if line == "L1":
    #     # Cambia la lista, etc.

    # Mezclamos la lista y tomamos 3
    random.shuffle(base_errors)
    selected = base_errors[:3]

    # Asignamos un conteo aleatorio
    top3 = []
    for err in selected:
        top3.append({
            "StopReason": err,
            "Count": random.randint(5, 25)
        })
    return jsonify(top3)

if __name__ == '__main__':
    app.run(debug=True)
