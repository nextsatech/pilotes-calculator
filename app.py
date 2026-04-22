from flask import Flask, render_template, request, jsonify
import math

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calcular', methods=['POST'])
def calcular():
    data = request.json
    
    forma = data.get('forma', 'circular')
    tipo_pilote = data.get('tipo_pilote', 'hincado')
    l = float(data.get('longitud', 0))
    fs_global = float(data.get('fs', 3.0))
    material = data.get('material', 'concreto')
    
    nx = int(data.get('grupo_nx', 1))
    ny = int(data.get('grupo_ny', 1))
    s_espacio = float(data.get('grupo_s', 0))
    n_pilotes = nx * ny
    
    if forma == 'circular':
        d = float(data.get('dim_d', 0))
        perimetro = math.pi * d
        area = (math.pi * d**2) / 4.0
        d_eq = d 
    elif forma == 'cuadrada':
        b = float(data.get('dim_b', 0))
        perimetro = 4.0 * b
        area = b**2
        d_eq = math.sqrt(4.0 * area / math.pi)
    else: 
        b = float(data.get('dim_b', 0))
        l_rect = float(data.get('dim_l', 0))
        perimetro = 2.0 * (b + l_rect)
        area = b * l_rect
        d_eq = math.sqrt(4.0 * area / math.pi)
        
    bg = (nx - 1) * s_espacio + d_eq
    lg = (ny - 1) * s_espacio + d_eq
    perimetro_g = 2.0 * (bg + lg)
    area_g = bg * lg
    
    if material == 'concreto':
        gamma_p = 24.0
        e_p = 21000000.0 
        delta_factor = 1.0
    elif material == 'madera':
        gamma_p = 9.0
        e_p = 10000000.0
        delta_factor = 0.8
    else: 
        gamma_p = 78.0
        e_p = 200000000.0
        delta_factor = 0.7
        
    peso = area * l * gamma_p
    
    estratos = data.get('estratos', [])
    
    for i, estrato in enumerate(estratos):
        tipo = estrato.get('tipo', 'cohesivo')
        ocr = float(estrato.get('ocr', 1.0))
        h_geo = float(estrato.get('h', 0))
        
        h_negativo = 0.0
        if tipo == 'cohesivo' and ocr <= 1.0:
            estrato_arriba_es_granular = (i > 0 and estratos[i-1].get('tipo') == 'granular')
            estrato_abajo_es_granular = (i < len(estratos)-1 and estratos[i+1].get('tipo') == 'granular')
            
            if estrato_arriba_es_granular:
                h_negativo = h_geo / 2.0
            elif estrato_abajo_es_granular:
                h_negativo = (2.0 * h_geo) / 3.0
                
        estrato['h_negativo_total'] = h_negativo

    qs_positivo = 0.0
    qs_negativo = 0.0
    qs_bloque_pos = 0.0
    peso_bloque = 0.0
    esfuerzos_efectivos = []
    detalles_friccion = []
    
    suma_e_h = 0.0
    suma_h = 0.0
    
    esfuerzo_tope_estrato = 0.0
    profundidad_techo = 0.0
    esfuerzo_punta = 0.0
    ultimo_estrato_tocado = None
    
    for i, estrato in enumerate(estratos):
        h_geologico = float(estrato.get('h', 0))
        
        if profundidad_techo >= l:
            break 
            
        h_penetracion = min(h_geologico, l - profundidad_techo)
        ultimo_estrato_tocado = estrato
        
        tipo = estrato.get('tipo', 'cohesivo')
        gamma_d = float(estrato.get('gamma_d', 0))
        gamma_sat = float(estrato.get('gamma_sat', 0))
        gamma_w = float(estrato.get('gamma_w', 9.81))
        ocr = float(estrato.get('ocr', 1.0))
        phi = float(estrato.get('phi', 0))
        su = float(estrato.get('su', 0))
        mod_e = float(estrato.get('mod_e', 0))
        h_negativo_total = estrato.get('h_negativo_total', 0.0)
        
        gamma_total_estrato = gamma_sat if gamma_sat > 0 else gamma_d
        peso_bloque += area_g * gamma_total_estrato * h_penetracion
        
        if gamma_sat > 0:
            gamma_eff = gamma_sat - gamma_w
        else:
            gamma_eff = gamma_d
            
        z_medio = h_penetracion / 2.0
        esfuerzo_medio = esfuerzo_tope_estrato + (gamma_eff * z_medio)
        esfuerzos_efectivos.append(esfuerzo_medio)
        
        fs_unit = 0.0
        ko_display = None
        
        if tipo == 'granular' or (tipo == 'cohesivo' and ocr > 1.0):
            phi_rad = math.radians(phi)
            delta_rad = phi_rad * delta_factor
            k_o_base = (1.0 - math.sin(phi_rad)) * math.sqrt(ocr)
            
            if tipo_pilote == 'preexcavado':
                k_o_base = k_o_base * 0.7 
                
            beta = k_o_base * math.tan(delta_rad)
            fs_unit = beta * esfuerzo_medio
            ko_display = k_o_base
        else:
            pa = 100.0
            ratio = su / pa
            if ratio <= 1.5:
                alpha = 0.55
            elif ratio <= 2.5:
                alpha = 0.55 - 0.1 * (ratio - 1.5)
            else:
                alpha = 0.45
            fs_unit = alpha * su
            ko_display = None
            
        h_penetracion_negativa = min(h_negativo_total, h_penetracion)
        h_penetracion_positiva = h_penetracion - h_penetracion_negativa
        
        qf_neg = fs_unit * perimetro * h_penetracion_negativa
        qf_pos = fs_unit * perimetro * h_penetracion_positiva
        
        qs_negativo += qf_neg
        qs_positivo += qf_pos
        qs_bloque_pos += fs_unit * perimetro_g * h_penetracion_positiva
        
        detalles_friccion.append({
            "estrato": i + 1,
            "phi": phi,
            "ko": ko_display,
            "area": perimetro * h_penetracion_positiva,
            "qf": qf_pos
        })
        
        esfuerzo_punta = esfuerzo_tope_estrato + (gamma_eff * h_penetracion)
        
        esfuerzo_tope_estrato += (gamma_eff * h_geologico)
        profundidad_techo += h_geologico
        
        suma_e_h += mod_e * h_penetracion
        suma_h += h_penetracion

    qb = 0.0
    qb_bloque = 0.0
    if ultimo_estrato_tocado:
        tipo_base = ultimo_estrato_tocado.get('tipo', 'cohesivo')
        ocr_base = float(ultimo_estrato_tocado.get('ocr', 1.0))
        
        if tipo_base == 'granular' or (tipo_base == 'cohesivo' and ocr_base > 1.0):
            phi_base = float(ultimo_estrato_tocado.get('phi', 0))
            phi_rad = math.radians(phi_base)
            
            psi = math.pi / 3.0
            nq_janbu = ((math.tan(phi_rad) + math.sqrt(1.0 + math.tan(phi_rad)**2))**2) * math.exp(2.0 * psi * math.tan(phi_rad))
            nq_muni = 0.6 * math.exp(0.126 * phi_base)
            
            nq = min(nq_janbu, nq_muni)
            
            if tipo_pilote == 'preexcavado':
                nq = nq * 0.5
            
            qb = nq * esfuerzo_punta * area 
            qb_bloque = nq * esfuerzo_punta * area_g
        else:
            su_base = float(ultimo_estrato_tocado.get('su', 0))
            nc = 9.0
            qb = nc * su_base * area
            qb_bloque = nc * su_base * area_g

    qu = qs_positivo + qb - peso
    qadm = qu / fs_global if fs_global > 0 else 0

    qu_bloque_total = qs_bloque_pos + qb_bloque - peso_bloque
    qu_single_total = qu * n_pilotes
    
    if n_pilotes > 1:
        qu_grupo = min(qu_single_total, qu_bloque_total)
        eficiencia = (qu_grupo / qu_single_total) * 100 if qu_single_total > 0 else 0
    else:
        qu_grupo = qu
        qu_bloque_total = qu
        eficiencia = 100.0

    rho_p = 0.0
    rho_es = 0.0
    rho_b = 0.0
    asentamiento_total = 0.0
    if ultimo_estrato_tocado:
        c_factor = 0.5
        if estratos[0].get('tipo') == 'cohesivo' and float(estratos[0].get('ocr', 1)) <= 1.0:
            c_factor = 0.7
            
        rho_p = c_factor * (qadm * l) / (e_p * area) if (e_p * area) > 0 else 0
        
        e_s0 = suma_e_h / suma_h if suma_h > 0 else 1.0
        if e_s0 <= 0: e_s0 = 1.0
            
        q_af = qs_positivo / fs_global if fs_global > 0 else 0
        i_factor = 0.5 + math.log10(l / d_eq) if d_eq > 0 else 1.0
        rho_es = (q_af / (e_s0 * l)) * i_factor if l > 0 else 0.0
        
        q_b_des = qb / fs_global if fs_global > 0 else 0
        v_b = float(ultimo_estrato_tocado.get('poisson', 0))
        e_b = float(ultimo_estrato_tocado.get('mod_e', 0))
        if e_b <= 0: e_b = 1.0
            
        r_b = d_eq / 2.0
        g_b = e_b / (2.0 * (1.0 + v_b))
        rho_b = (q_b_des / (r_b * g_b)) * ((1.0 - v_b) / 4.0) if r_b > 0 and g_b > 0 else 0.0
        
        asentamiento_total = (rho_p + rho_es + rho_b) * 1000.0

    return jsonify({
        "qs_pos": qs_positivo,
        "qs_neg": qs_negativo,
        "qb": qb,
        "peso": peso,
        "qu": qu,
        "qadm": qadm,
        "rho_p": rho_p * 1000.0,
        "rho_es": rho_es * 1000.0,
        "rho_b": rho_b * 1000.0,
        "asentamiento_mm": asentamiento_total,
        "n_pilotes": n_pilotes,
        "qu_single_total": qu_single_total,
        "qu_bloque": qu_bloque_total,
        "qu_grupo": qu_grupo,
        "eficiencia": eficiencia,
        "detalles_friccion": detalles_friccion
    })

if __name__ == '__main__':
    app.run(debug=True)