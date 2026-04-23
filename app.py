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
    
    n_pilotes = int(data.get('n_pilotes', 1))
    perimetro_g = float(data.get('perimetro_g', 0))
    area_g = float(data.get('area_g', 0))
    peso_g_input = float(data.get('peso_g', 0))
    bg_g = float(data.get('bg_g', 0))
    lg_g = float(data.get('lg_g', 0))
    
    longitud_g = float(data.get('longitud_g', 0))
    if longitud_g <= 0:  
        longitud_g = l
    
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
        
    d_eq_g = math.sqrt(4.0 * area_g / math.pi) if area_g > 0 else 0

    if material == 'concreto':
        gamma_p = 24.0
        e_p = 21000000.0 
        delta_factor = 1.0
    elif material == 'madera':
        gamma_p = 9.0
        e_p = 10000000.0
        delta_factor = 1.0
    else: 
        gamma_p = 78.0
        e_p = 200000000.0
        delta_factor = 0.8
        
    peso = area * l * gamma_p
    
    estratos = data.get('estratos', [])
    estratos_cons = data.get('estratos_cons', [])
    
    c_factor = 0.5
    if len(estratos) > 0 and estratos[0].get('tipo', 'cohesivo') == 'cohesivo' and float(estratos[0].get('ocr', 1.0)) <= 1.0:
        c_factor = 0.7
    
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
    
    rho_p_total = 0.0
    rho_es_total = 0.0
    rho_p_g_total = 0.0
    rho_es_g_total = 0.0
    
    detalles_friccion = []
    detalles_asentamiento = []
    detalles_asentamiento_g = []
    
    esfuerzo_tope_estrato = 0.0
    profundidad_techo = 0.0
    esfuerzo_punta = 0.0
    esfuerzo_punta_g = 0.0
    
    ultimo_estrato_tocado = None
    ultimo_estrato_tocado_g = None
    
    for i, estrato in enumerate(estratos):
        h_geologico = float(estrato.get('h', 0))
        
        if profundidad_techo >= l and profundidad_techo >= longitud_g:
            break 
            
        h_penetracion = 0.0
        if profundidad_techo < l:
            h_penetracion = min(h_geologico, l - profundidad_techo)
            
        h_penetracion_g = 0.0
        if profundidad_techo < longitud_g:
            h_penetracion_g = min(h_geologico, longitud_g - profundidad_techo)

        tipo = estrato.get('tipo', 'cohesivo')
        gamma_d = float(estrato.get('gamma_d', 0))
        gamma_sat = float(estrato.get('gamma_sat', 0))
        gamma_w = float(estrato.get('gamma_w', 9.81))
        ocr = float(estrato.get('ocr', 1.0))
        phi = float(estrato.get('phi', 0))
        su = float(estrato.get('su', 0))
        mod_e = float(estrato.get('mod_e', 0))
        h_negativo_total = estrato.get('h_negativo_total', 0.0)
        
        gamma_eff = (gamma_sat - gamma_w) if gamma_sat > 0 else gamma_d
            
        fs_unit = 0.0
        fs_unit_g = 0.0
        ko_display = None
        esfuerzo_medio = 0.0
        
        if tipo == 'granular' or (tipo == 'cohesivo' and ocr > 1.0):
            phi_rad = math.radians(phi)
            delta_rad = phi_rad * delta_factor
            k_o_base = (1.0 - math.sin(phi_rad)) * math.sqrt(ocr)
            if tipo_pilote == 'preexcavado':
                k_o_base = k_o_base * 0.7 
            beta = k_o_base * math.tan(delta_rad)
            
            if h_penetracion > 0:
                z_medio = h_penetracion / 2.0
                esfuerzo_medio = esfuerzo_tope_estrato + (gamma_eff * z_medio)
                fs_unit = beta * esfuerzo_medio
            
            if h_penetracion_g > 0:
                z_medio_g = h_penetracion_g / 2.0
                esfuerzo_medio_g = esfuerzo_tope_estrato + (gamma_eff * z_medio_g)
                fs_unit_g = beta * esfuerzo_medio_g
                
            ko_display = k_o_base
        else:
            pa = 100.0
            ratio = su / pa
            
            if ratio <= 1.5: alpha = 0.50
            elif ratio <= 2.5: alpha = 0.50 - 0.1 * (ratio - 1.5)
            else: alpha = 0.40
            
            fs_unit = alpha * su
            fs_unit_g = alpha * su
            if h_penetracion > 0:
                esfuerzo_medio = esfuerzo_tope_estrato + (gamma_eff * (h_penetracion / 2.0))
            
        h_penetracion_negativa = min(h_negativo_total, h_penetracion)
        h_penetracion_positiva = h_penetracion - h_penetracion_negativa
        
        h_penetracion_negativa_g = min(h_negativo_total, h_penetracion_g)
        h_penetracion_positiva_g = h_penetracion_g - h_penetracion_negativa_g
        
        qf_neg = fs_unit * perimetro * h_penetracion_negativa
        qf_pos = fs_unit * perimetro * h_penetracion_positiva
        qs_negativo += qf_neg
        qs_positivo += qf_pos
        
        qf_bloque_pos_i = 0.0
        if n_pilotes > 1 and h_penetracion_positiva_g > 0:
            qf_bloque_pos_i = fs_unit_g * perimetro_g * h_penetracion_positiva_g
            qs_bloque_pos += qf_bloque_pos_i
        
        qf_adm_estrato = qf_pos / fs_global if fs_global > 0 else 0
        qf_adm_bloque_estrato = qf_bloque_pos_i / fs_global if fs_global > 0 else 0
        
        rho_p_i = 0.0
        rho_es_i = 0.0
        if h_penetracion_positiva > 0:
            area_estrato = perimetro * h_penetracion_positiva
            if e_p > 0 and area > 0:
                rho_p_i = c_factor * (qf_adm_estrato * h_penetracion_positiva) / (e_p * area)
            if mod_e > 0:
                i_factor_i = 0.5 + math.log10(h_penetracion_positiva / d_eq) if d_eq > 0 else 1.0
                rho_es_i = (qf_adm_estrato / (mod_e * h_penetracion_positiva)) * i_factor_i
                
        rho_p_g_i = 0.0
        rho_es_g_i = 0.0
        if n_pilotes > 1 and h_penetracion_positiva_g > 0:
            if e_p > 0 and area_g > 0:
                rho_p_g_i = c_factor * (qf_adm_bloque_estrato * h_penetracion_positiva_g) / (e_p * area_g)
            if mod_e > 0:
                i_factor_g = 0.5 + math.log10(h_penetracion_positiva_g / d_eq_g) if d_eq_g > 0 else 1.0
                rho_es_g_i = (qf_adm_bloque_estrato / (mod_e * h_penetracion_positiva_g)) * i_factor_g
                
        rho_p_total += rho_p_i
        rho_es_total += rho_es_i
        rho_p_g_total += rho_p_g_i
        rho_es_g_total += rho_es_g_i

        if h_penetracion > 0:
            ultimo_estrato_tocado = estrato
            esfuerzo_punta = esfuerzo_tope_estrato + (gamma_eff * h_penetracion)
            detalles_asentamiento.append({
                "estrato": i + 1,
                "rho_p_mm": rho_p_i * 1000.0,
                "rho_es_mm": rho_es_i * 1000.0
            })
            detalles_friccion.append({
                "estrato": i + 1,
                "phi": phi,
                "ko": ko_display,
                "esfuerzo_v": esfuerzo_medio,
                "area": perimetro * h_penetracion_positiva,
                "qf": qf_pos
            })
            
        if h_penetracion_g > 0 and n_pilotes > 1:
            ultimo_estrato_tocado_g = estrato
            esfuerzo_punta_g = esfuerzo_tope_estrato + (gamma_eff * h_penetracion_g)
            detalles_asentamiento_g.append({
                "estrato": i + 1,
                "rho_p_mm": rho_p_g_i * 1000.0,
                "rho_es_mm": rho_es_g_i * 1000.0
            })
        
        profundidad_techo += h_geologico
        esfuerzo_tope_estrato += (gamma_eff * h_geologico)

    qb = 0.0
    if ultimo_estrato_tocado:
        tipo_base = ultimo_estrato_tocado.get('tipo', 'cohesivo')
        ocr_base = float(ultimo_estrato_tocado.get('ocr', 1.0))
        
        if tipo_base == 'granular' or (tipo_base == 'cohesivo' and ocr_base > 1.0):
            phi_base = float(ultimo_estrato_tocado.get('phi', 0))
            phi_rad = math.radians(phi_base)
            psi = math.pi / 3.0
            nq_janbu = ((math.tan(phi_rad) + math.sqrt(1.0 + math.tan(phi_rad)**2))**2) * math.exp(2.0 * psi * math.tan(phi_rad))
            nq_muni = 0.6 * math.exp(0.126 * phi_base)
            nq = min(nq_janbu, nq_muni) * (0.5 if tipo_pilote == 'preexcavado' else 1.0)
            qb = nq * esfuerzo_punta * area 
        else:
            su_base = float(ultimo_estrato_tocado.get('su', 0))
            qb = 9.0 * su_base * area

    qb_bloque = 0.0
    if n_pilotes > 1 and ultimo_estrato_tocado_g:
        tipo_base_g = ultimo_estrato_tocado_g.get('tipo', 'cohesivo')
        ocr_base_g = float(ultimo_estrato_tocado_g.get('ocr', 1.0))
        
        if tipo_base_g == 'granular' or (tipo_base_g == 'cohesivo' and ocr_base_g > 1.0):
            phi_base_g = float(ultimo_estrato_tocado_g.get('phi', 0))
            phi_rad_g = math.radians(phi_base_g)
            psi = math.pi / 3.0
            nq_janbu_g = ((math.tan(phi_rad_g) + math.sqrt(1.0 + math.tan(phi_rad_g)**2))**2) * math.exp(2.0 * psi * math.tan(phi_rad_g))
            nq_muni_g = 0.6 * math.exp(0.126 * phi_base_g)
            nq_g = min(nq_janbu_g, nq_muni_g) * (0.5 if tipo_pilote == 'preexcavado' else 1.0)
            qb_bloque = nq_g * esfuerzo_punta_g * area_g 
        else:
            su_base_g = float(ultimo_estrato_tocado_g.get('su', 0))
            qb_bloque = 9.0 * su_base_g * area_g

    qu = qs_positivo + qb - peso
    qadm = qu / fs_global if fs_global > 0 else 0

    qu_bloque_total = 0.0
    qadm_grupo = 0.0
    eficiencia = 1.0
    
    if n_pilotes > 1:
        qu_bloque_total = qs_bloque_pos + qb_bloque - peso_g_input
        qadm_grupo = qu_bloque_total / fs_global if fs_global > 0 else 0
        qadm_ind_total = qadm * n_pilotes
        eficiencia = (qadm_grupo / qadm_ind_total) if qadm_ind_total > 0 else 0

    rho_b = 0.0
    if ultimo_estrato_tocado:
        q_b_des = qb / fs_global if fs_global > 0 else 0
        v_b = float(ultimo_estrato_tocado.get('poisson', 0))
        e_b = float(ultimo_estrato_tocado.get('mod_e', 0))
        if e_b <= 0: e_b = 1.0
        r_b = d_eq / 2.0
        g_b = e_b / (2.0 * (1.0 - v_b)) if v_b != 1.0 else e_b / 2.0
        if g_b > 0 and r_b > 0:
            rho_b = (q_b_des / (r_b * g_b)) * ((1.0 - v_b) / 4.0)

    rho_b_g = 0.0
    if n_pilotes > 1 and ultimo_estrato_tocado_g:
        q_b_des_g = qb_bloque / fs_global if fs_global > 0 else 0
        v_b_g = float(ultimo_estrato_tocado_g.get('poisson', 0))
        e_b_g = float(ultimo_estrato_tocado_g.get('mod_e', 0))
        if e_b_g <= 0: e_b_g = 1.0
        r_b_g = d_eq_g / 2.0
        g_b_g = e_b_g / (2.0 * (1.0 - v_b_g)) if v_b_g != 1.0 else e_b_g / 2.0
        if g_b_g > 0 and r_b_g > 0:
            rho_b_g = (q_b_des_g / (r_b_g * g_b_g)) * ((1.0 - v_b_g) / 4.0)

    asentamiento_total = (rho_p_total + rho_es_total + rho_b) * 1000.0
    asentamiento_g_total = (rho_p_g_total + rho_es_g_total + rho_b_g) * 1000.0

    detalles_cons = []
    asentamiento_cons_total = 0.0

    if n_pilotes > 1 and qadm_grupo > 0:
        for i, estrato_c in enumerate(estratos_cons):
            z_cons = float(estrato_c.get('z', 0))
            h_cons = float(estrato_c.get('h', 0))
            cc_cons = float(estrato_c.get('cc', 0))
            cs_cons = float(estrato_c.get('cs', 0))
            e_cons = float(estrato_c.get('e', 0))
            ocr_cons = float(estrato_c.get('ocr', 1.0))
            sigma0_cons = float(estrato_c.get('sigma0', 0))
            sigmac_cons = float(estrato_c.get('sigmac', 0))
            
            delta_sigma = 0.0
            if (bg_g + z_cons) > 0 and (lg_g + z_cons) > 0:
                delta_sigma = qadm_grupo / ((bg_g + z_cons) * (lg_g + z_cons))
                
            sc_m = 0.0
            if sigma0_cons > 0 and (1 + e_cons) > 0:
                if ocr_cons == 1.0:
                    sc_m = (cc_cons * h_cons / (1 + e_cons)) * math.log10((delta_sigma + sigma0_cons) / sigma0_cons)
                elif ocr_cons > 1.0:
                    if (delta_sigma + sigma0_cons) <= sigmac_cons:
                        sc_m = (cs_cons * h_cons / (1 + e_cons)) * math.log10((delta_sigma + sigma0_cons) / sigma0_cons)
                    else:
                        sc_part1 = (cs_cons * h_cons / (1 + e_cons)) * math.log10(sigmac_cons / sigma0_cons) if sigmac_cons > 0 else 0
                        sc_part2 = (cc_cons * h_cons / (1 + e_cons)) * math.log10((delta_sigma + sigma0_cons) / sigmac_cons) if sigmac_cons > 0 else 0
                        sc_m = sc_part1 + sc_part2
                else:
                    sc_m = (cc_cons * h_cons / (1 + e_cons)) * math.log10((delta_sigma + sigma0_cons) / sigma0_cons)
            
            sc_mm = sc_m * 1000.0
            asentamiento_cons_total += sc_mm
            
            detalles_cons.append({
                "estrato": i + 1,
                "delta_sigma": delta_sigma,
                "sc_mm": sc_mm
            })

    return jsonify({
        "qs_pos": qs_positivo,
        "qs_neg": qs_negativo,
        "qb": qb,
        "peso": peso,
        "qu": qu,
        "qadm": qadm,
        "rho_p": rho_p_total * 1000.0,
        "rho_es": rho_es_total * 1000.0,
        "rho_b": rho_b * 1000.0,
        "asentamiento_mm": asentamiento_total,
        "n_pilotes": n_pilotes,
        "qs_bloque": qs_bloque_pos,
        "qb_bloque": qb_bloque,
        "peso_bloque": peso_g_input,
        "qu_bloque": qu_bloque_total,
        "qadm_grupo": qadm_grupo,
        "eficiencia": eficiencia,
        "rho_p_g": rho_p_g_total * 1000.0,
        "rho_es_g": rho_es_g_total * 1000.0,
        "rho_b_g": rho_b_g * 1000.0,
        "asentamiento_g_mm": asentamiento_g_total,
        "asentamiento_cons_mm": asentamiento_cons_total,
        "detalles_friccion": detalles_friccion,
        "detalles_asentamiento": detalles_asentamiento,
        "detalles_asentamiento_g": detalles_asentamiento_g,
        "detalles_cons": detalles_cons
    })

if __name__ == '__main__':
    app.run(debug=True)