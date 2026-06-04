import { useState, useEffect } from "react";

const LEVELS = {
  principiante: {
    id: "principiante",
    title: "Principiante",
    icon: "🌱",
    color: "#10b981",
    bg: "#052e16",
    desc: "Fundamentos sólidos. Entender la teoría sin errores.",
    examTitle: "Examen de Principiante",
    examDesc: "Demuestra que dominas la estructura, las reglas y los patrones básicos.",
    modules: [
      {
        id: "M1", title: "Estructura del Mercado", icon: "🏗️",
        concepts: [
          { id: "1.1", title: "Ciclo completo", subtitle: "5 ondas impulsivas + 3 correctivas = 8 ondas", status: "completed", date: "2026-03-15" },
          { id: "1.2", title: "Ondas impulsivas", subtitle: "O1, O3, O5 a favor — O2, O4 retrocesos", status: "completed", date: "2026-03-15" },
          { id: "1.3", title: "Ondas correctivas", subtitle: "A-B-C en contra de la tendencia", status: "completed", date: "2026-03-15" },
          { id: "1.4", title: "Estructura ≠ dirección", subtitle: "5 ondas = impulso, 3 ondas = corrección sin importar dirección", status: "completed", date: "2026-03-15" },
        ]
      },
      {
        id: "M2", title: "Las 3 Reglas Inviolables", icon: "📜",
        concepts: [
          { id: "2.1", title: "Regla 1", subtitle: "O2 no pasa el inicio de O1", status: "completed", date: "2026-03-15" },
          { id: "2.2", title: "Regla 2", subtitle: "O3 nunca es la más corta", status: "completed", date: "2026-03-15" },
          { id: "2.3", title: "Regla 3", subtitle: "O4 no entra en el rango de O1", status: "completed", date: "2026-03-15" },
          { id: "2.4", title: "Regla universal", subtitle: "Alcista=menor / Bajista=mayor + punto de referencia", status: "completed", date: "2026-03-15" },
          { id: "2.5", title: "Validación completa", subtitle: "Verificar las 3 reglas en cualquier conteo", status: "completed", date: "2026-03-15" },
        ]
      },
      {
        id: "M3", title: "Patrones Esenciales", icon: "📊",
        concepts: [
          { id: "3.1", title: "Extensiones", subtitle: "Una onda se estira — O3 más común en BTC", status: "completed", date: "2026-03-15" },
          { id: "3.2", title: "Truncamientos", subtitle: "O5 no supera extremo de O3 — señal de debilidad", status: "completed", date: "2026-03-15" },
          { id: "3.3", title: "Diagonales", subtitle: "Triángulos inclinados: inicial (O1) y final (O5) — excepción R3", status: "completed", date: "2026-04-01" },
          { id: "3.4", title: "Fibonacci básico", subtitle: "Niveles 0.618, 0.382, 1.618 y su relación con ondas", status: "completed", date: "2026-04-01" },
          { id: "3.5", title: "Grados de onda", subtitle: "Ondas dentro de ondas — fractalidad del mercado", status: "completed", date: "2026-04-01" },
        ]
      }
    ],
    exam: [
      { q: "¿Cuántas ondas tiene un impulso y cuántas una corrección?", type: "open" },
      { q: "BTC sube de $50K a $65K en 3 subondas. ¿Impulso o corrección?", type: "scenario" },
      { q: "O1: $40K→$48K, O2: baja a $39K. ¿Válido?", type: "rule_check" },
      { q: "O1=$5K, O3=$3K, O5=$7K. ¿Qué regla se viola?", type: "rule_check" },
      { q: "Impulso bajista. O1: $80K→$72K. O4 sube a $73K. ¿Válido?", type: "rule_check" },
      { q: "O3 recorrió el doble que O1 y O5. ¿Qué patrón es?", type: "pattern" },
      { q: "O5 no superó el máximo de O3. ¿Qué patrón es y qué esperas después?", type: "pattern" },
      { q: "Ves una cuña en O5 donde O4 se solapa con O1. ¿Qué es y qué implica?", type: "pattern" },
      { q: "¿Por qué un truncamiento solo es válido si O3 fue extensión?", type: "conceptual" },
      { q: "Explica la regla universal para R1 y R3 en alcista y bajista.", type: "conceptual" },
    ]
  },
  amateur: {
    id: "amateur",
    title: "Amateur",
    icon: "⚡",
    color: "#f59e0b",
    bg: "#2a1f00",
    desc: "Aplicación práctica. Contar ondas en gráficos reales y combinar con liquidez.",
    examTitle: "Examen Amateur",
    examDesc: "Demuestra que puedes analizar gráficos reales y combinar Elliott con zonas de liquidación.",
    modules: [
      {
        id: "M4", title: "Correcciones Avanzadas", icon: "🔄",
        concepts: [
          { id: "4.1", title: "Zigzag (5-3-5)", subtitle: "Corrección agresiva — A y C son impulsos", status: "completed", date: "2026-04-01" },
          { id: "4.2", title: "Plana (3-3-5)", subtitle: "Corrección lateral — A y B son correctivas", status: "completed", date: "2026-04-01" },
          { id: "4.3", title: "Triángulo (3-3-3-3-3)", subtitle: "5 ondas correctivas convergentes — aparece en O4 o B", status: "completed", date: "2026-04-01" },
          { id: "4.4", title: "Correcciones complejas", subtitle: "Dobles y triples combinaciones (W-X-Y, W-X-Y-X-Z)", status: "completed", date: "2026-04-01" },
          { id: "4.5", title: "Alternancia", subtitle: "Si O2 es agresiva, O4 es lateral (y viceversa)", status: "completed", date: "2026-04-01" },
        ]
      },
      {
        id: "M5", title: "Fibonacci Avanzado", icon: "🔢",
        concepts: [
          { id: "5.1", title: "Retrocesos de Fibonacci", subtitle: "O2 típica: 50%-61.8% — O4 típica: 38.2%", status: "completed", date: "2026-04-05" },
          { id: "5.2", title: "Extensiones de Fibonacci", subtitle: "Proyectar O3 y O5 con ratios 1.618, 2.618", status: "completed", date: "2026-04-05" },
          { id: "5.3", title: "Fibonacci en correcciones", subtitle: "Targets de A-B-C con ratios de Fibonacci", status: "completed", date: "2026-04-05" },
          { id: "5.4", title: "Confluencia de niveles", subtitle: "Cuando múltiples Fibonacci coinciden = zona de alta probabilidad", status: "completed", date: "2026-04-05" },
        ]
      },
      {
        id: "M6", title: "Conteo en Gráficos Reales", icon: "📈",
        concepts: [
          { id: "6.1", title: "Timeframes", subtitle: "Macro (semanal/mensual) vs micro (4h/1h) — de mayor a menor", status: "completed", date: "2026-04-10" },
          { id: "6.2", title: "Conteo en BTC", subtitle: "Práctica de conteo completo en Bitcoin", status: "completed", date: "2026-04-10" },
          { id: "6.3", title: "Conteo en ETH", subtitle: "Práctica de conteo completo en Ethereum", status: "completed", date: "2026-04-10" },
          { id: "6.4", title: "Errores comunes de conteo", subtitle: "Trampas típicas y cómo evitarlas", status: "completed", date: "2026-04-10" },
          { id: "6.5", title: "Conteos alternativos", subtitle: "Siempre tener plan A y plan B", status: "completed", date: "2026-04-10" },
        ]
      },
      {
        id: "M7", title: "Zonas de Liquidación", icon: "💧",
        concepts: [
          { id: "7.1", title: "Qué es la liquidez", subtitle: "Stop losses acumulados = imán para el precio", status: "completed", date: "2026-04-15" },
          { id: "7.2", title: "Liquidez de máximos/mínimos", subtitle: "Buy-side y sell-side liquidity", status: "completed", date: "2026-04-15" },
          { id: "7.3", title: "Mapas de liquidación", subtitle: "Leer heatmaps de liquidez en exchanges", status: "completed", date: "2026-04-15" },
          { id: "7.4", title: "Elliott + Liquidez", subtitle: "Las ondas buscan liquidez — O3 barre stops, O5 busca último pool", status: "completed", date: "2026-04-15" },
        ]
      }
    ],
    exam: [
      { q: "Dibuja la estructura interna de un Zigzag vs una Plana.", type: "structure" },
      { q: "¿En qué posiciones aparece típicamente un triángulo?", type: "open" },
      { q: "O2 fue un zigzag agresivo. ¿Qué tipo de corrección esperas en O4?", type: "scenario" },
      { q: "BTC corrige de $100K. ¿Cuáles son los niveles de Fibonacci clave para O2?", type: "fibonacci" },
      { q: "Tienes O1 y O2 completas. ¿Cómo proyectas el target de O3 con Fibonacci?", type: "fibonacci" },
      { q: "Escenario de conteo real: identifica las 5 ondas en la estructura dada.", type: "chart" },
      { q: "¿Qué es buy-side liquidity y dónde la encuentras?", type: "open" },
      { q: "¿Por qué O3 tiende a barrer los stop losses de O1?", type: "conceptual" },
      { q: "Presenta un conteo de BTC con plan A y plan B. ¿Qué invalida cada uno?", type: "analysis" },
      { q: "Marca en un escenario dónde está la liquidez y cómo la onda la busca.", type: "combined" },
    ]
  },
  experto: {
    id: "experto",
    title: "Experto",
    icon: "🏆",
    color: "#a855f7",
    bg: "#1a0a2e",
    desc: "Operativa real. Estrategia completa para operar con criterio propio.",
    examTitle: "Examen de Experto",
    examDesc: "Demuestra que puedes crear un plan de trading completo usando Elliott + Liquidez.",
    modules: [
      {
        id: "M8", title: "Estrategia de Entrada", icon: "🎯",
        concepts: [
          { id: "8.1", title: "Entradas en O3", subtitle: "Comprar al final de O2 — la entrada de mayor probabilidad", status: "completed", date: "2026-05-09" },
          { id: "8.2", title: "Entradas en O5", subtitle: "Operar la última onda con precaución", status: "completed", date: "2026-05-14" },
          { id: "8.3", title: "Entradas en corrección", subtitle: "Operar el ABC — contratendencia con gestión estricta", status: "completed", date: "2026-05-15" },
          { id: "8.4", title: "Confluencia Elliott + Fib + Liquidez", subtitle: "Cuando todo se alinea = entrada A+", status: "completed", date: "2026-05-15" },
        ]
      },
      {
        id: "M9", title: "Gestión de Riesgo", icon: "🛡️",
        concepts: [
          { id: "9.1", title: "Stop loss con Elliott", subtitle: "Dónde poner el stop según la onda que operas", status: "completed", date: "2026-05-23" },
          { id: "9.2", title: "Take profit con Fibonacci", subtitle: "Targets basados en extensiones y retrocesos", status: "completed", date: "2026-05-23" },
          { id: "9.3", title: "Ratio riesgo/beneficio", subtitle: "Mínimo 1:2 — cómo calcularlo con ondas", status: "completed", date: "2026-05-23" },
          { id: "9.4", title: "Tamaño de posición", subtitle: "Cuánto arriesgar por trade — % de cuenta", status: "completed", date: "2026-05-23" },
          { id: "9.5", title: "Invalidación y plan B", subtitle: "Cuándo tu conteo está mal y qué hacer", status: "completed", date: "2026-05-23" },
        ]
      },
      {
        id: "M10", title: "Plan de Trading Completo", icon: "📋",
        concepts: [
          { id: "10.1", title: "Análisis top-down", subtitle: "Macro → micro: semanal → diario → 4h → 1h", status: "completed", date: "2026-05-23" },
          { id: "10.2", title: "Selección de activo", subtitle: "BTC vs ETH vs altcoins — cuándo operar cada uno", status: "completed", date: "2026-05-23" },
          { id: "10.3", title: "Timing de mercado", subtitle: "Ciclos de Elliott en macro — dónde estamos en el ciclo grande", status: "completed", date: "2026-05-23" },
          { id: "10.4", title: "Diario de operaciones", subtitle: "Documentar cada trade con conteo, entrada, salida, resultado", status: "completed", date: "2026-05-23" },
          { id: "10.5", title: "Psicología del trader", subtitle: "Disciplina, paciencia, gestión emocional con Elliott como ancla", status: "completed", date: "2026-05-23" },
        ]
      },
      {
        id: "M11", title: "Operativa en Vivo", icon: "🔴",
        concepts: [
          { id: "11.1", title: "Caso práctico BTC", subtitle: "Análisis completo + plan de trade + ejecución simulada", status: "completed", date: "2026-05-24" },
          { id: "11.2", title: "Caso práctico ETH", subtitle: "Análisis completo + plan de trade + ejecución simulada", status: "completed", date: "2026-05-24" },
          { id: "11.3", title: "Caso práctico Altcoin", subtitle: "Aplicar todo en un activo de menor capitalización", status: "completed", date: "2026-05-30" },
          { id: "11.4", title: "Revisión y autocrítica", subtitle: "Evaluar tus propios análisis — qué mejorar", status: "completed", date: "2026-05-30" },
        ]
      }
    ],
    exam: [
      { q: "Presenta un análisis top-down completo de BTC: semanal, diario, 4h.", type: "full_analysis" },
      { q: "Identifica una entrada en O3 con confluencia de Fib + Liquidez. Define stop, target, ratio R/B.", type: "trade_plan" },
      { q: "El precio invalidó tu conteo principal. ¿Cuál es tu plan B y cómo ajustas la posición?", type: "risk_mgmt" },
      { q: "Crea un plan de trading completo para la próxima semana con BTC y ETH.", type: "full_plan" },
      { q: "Analiza un trade que salió mal. ¿Qué falló en el conteo, la entrada o la gestión?", type: "review" },
    ]
  },
  proptrader: {
    id: "proptrader",
    title: "Prop Trader",
    icon: "🎯",
    color: "#06b6d4",
    bg: "#021a1f",
    desc: "Pasar y operar cuentas de fondeo reales. Análisis en vivo con Claude como mentor.",
    examTitle: "Evaluación Prop Trader",
    examDesc: "Demuestra que puedes pasar y mantener una cuenta de fondeo usando Elliott + gestión de riesgo.",
    modules: [
      {
        id: "M12", title: "Entendiendo las Prop Firms", icon: "🏦",
        concepts: [
          { id: "12.1", title: "Cómo funcionan las evaluaciones", subtitle: "Fases, reglas y objetivos de cada tipo de cuenta", status: "locked", date: null },
          { id: "12.2", title: "Reglas clave: drawdown y profit target", subtitle: "Daily drawdown, max drawdown, días mínimos de trading", status: "locked", date: null },
          { id: "12.3", title: "Comparativa de firmas", subtitle: "DNA Funded, BrightFunded, FXIFY, Topstep, Tradeify, Apex", status: "locked", date: null },
          { id: "12.4", title: "Elegir la firma correcta", subtitle: "Según tu estilo, activo y capital disponible", status: "locked", date: null },
        ]
      },
      {
        id: "M13", title: "Estrategia para Pasar la Evaluación", icon: "🎯",
        concepts: [
          { id: "13.1", title: "Gestión de drawdown en evaluación", subtitle: "Nunca perder más del X% diario — cómo calcularlo", status: "locked", date: null },
          { id: "13.2", title: "Riesgo por día y por trade en fondeo", subtitle: "Adaptar el 1-2% de cuenta a las reglas de la firma", status: "locked", date: null },
          { id: "13.3", title: "Cuándo operar y cuándo no", subtitle: "Días de noticias, volatilidad y reglas de la firma", status: "locked", date: null },
          { id: "13.4", title: "Plan de 30 días para pasar $10K+", subtitle: "Roadmap semana a semana con Elliott + gestión", status: "locked", date: null },
        ]
      },
      {
        id: "M14", title: "Operando la Cuenta Fondeada", icon: "💰",
        concepts: [
          { id: "14.1", title: "Evaluación vs cuenta real fondeada", subtitle: "Diferencias de psicología y gestión entre fases", status: "locked", date: null },
          { id: "14.2", title: "Mantener la cuenta sin perderla", subtitle: "Gestión conservadora para preservar el fondeo", status: "locked", date: null },
          { id: "14.3", title: "Escalar de $10K a cuentas mayores", subtitle: "Cuándo y cómo pedir más capital", status: "locked", date: null },
          { id: "14.4", title: "Impuestos y finanzas para traders US", subtitle: "Cómo declarar ingresos de prop firms en Estados Unidos", status: "locked", date: null },
        ]
      }
    ],
    exam: [
      { q: "Diseña un plan de 30 días para pasar una evaluación de $10K. Incluye riesgo diario, días de trading y activos.", type: "full_plan" },
      { q: "¿Qué firma elegirías para operar BTC/ETH con Elliott y por qué? Justifica con sus reglas específicas.", type: "analysis" },
      { q: "Estás al 80% del profit target pero al 70% del max drawdown. ¿Qué haces?", type: "risk_mgmt" },
      { q: "Presenta un pre-análisis completo de un trade real usando el documento de pre-análisis.", type: "live_trade" },
      { q: "Presenta el post-análisis de un trade cerrado. ¿Qué aprendiste y qué cambias?", type: "review" },
    ]
  }
};

const MISTAKES = [
  { id: 1, concept: "1.4", error: "Confundí dirección del precio con estructura", lesson: "La cantidad de ondas define impulso/corrección, NO la dirección", date: "2026-03-15" },
  { id: 2, concept: "2.3", error: "R3 en bajistas: confundí dentro/fuera de zona", lesson: "Bajista: O4 no puede ser MAYOR que final O1", date: "2026-03-15" },
  { id: 3, concept: "2.2", error: "R2: confundí 'no la más corta' con 'debe ser la más larga'", lesson: "O3 solo no puede ser la MÁS CORTA de O1, O3 y O5", date: "2026-03-15" },
  { id: 4, concept: "3.1", error: "No verifiqué R2 antes de declarar extensión", lesson: "SIEMPRE verificar reglas antes de patrones", date: "2026-03-15" },
  { id: 5, concept: "5.x", error: "Invertí los operandos en división Fibonacci", lesson: "ratio = retroceso ÷ recorrido — siempre retroceso sobre recorrido", date: "2026-04-05" },
  { id: 6, concept: "6.3", error: "Quise medir C desde fin de B en lugar de inicio de la corrección", lesson: "C SIEMPRE se mide desde INICIO de la corrección, nunca desde fin de B", date: "2026-04-10" },
  { id: 7, concept: "6.x", error: "Tendencia a forzar 5 ondas donde hay 3", lesson: "Contar subondas internas para confirmar estructura antes de declarar impulso", date: "2026-04-10" },
  { id: 8, concept: "Examen Amateur P9", error: "Conteos alternativos sin invalidaciones específicas definidas", lesson: "Todo conteo alternativo necesita su propio precio de invalidación — sin ese número el plan B no sirve", date: "2026-04-15" },
];

const PILLARS = [
  { id: 1, title: "Estructura del Mercado", icon: "🏗️", desc: "Impulso=5 / Corrección=3 / Estructura > dirección", level: "principiante", unlockedBy: "1.4", locked: false },
  { id: 2, title: "Las 3 Reglas Sagradas", icon: "📜", desc: "R1+R2+R3 = la base inviolable de todo conteo", level: "principiante", unlockedBy: "2.5", locked: false },
  { id: 3, title: "Extensiones", icon: "📏", desc: "Una onda se estira — O3 más común — solo UNA por impulso", level: "principiante", unlockedBy: "3.1", locked: false },
  { id: 4, title: "Truncamientos", icon: "⚡", desc: "O5 falla = debilidad → corrección agresiva viene", level: "principiante", unlockedBy: "3.2", locked: false },
  { id: 5, title: "Diagonales", icon: "📐", desc: "Triángulos inclinados: inicial(O1) y final(O5) — excepción R3", level: "principiante", unlockedBy: "3.3", locked: false },
  { id: 6, title: "Fibonacci", icon: "🔢", desc: "Los ratios que gobiernan las proporciones de las ondas", level: "principiante", unlockedBy: "3.4", locked: false },
  { id: 7, title: "Fractalidad", icon: "🔬", desc: "Ondas dentro de ondas — el mercado es un fractal", level: "principiante", unlockedBy: "3.5", locked: false },
  { id: 8, title: "Correcciones Complejas", icon: "🔄", desc: "Zigzag, plana, triángulo, combinaciones W-X-Y", level: "amateur", unlockedBy: "4.4", locked: false },
  { id: 9, title: "Fibonacci Maestro", icon: "📐", desc: "Retrocesos, extensiones y confluencia de niveles", level: "amateur", unlockedBy: "5.4", locked: false },
  { id: 10, title: "Lectura de Gráficos", icon: "📈", desc: "Conteo correcto en timeframes múltiples", level: "amateur", unlockedBy: "6.5", locked: false },
  { id: 11, title: "Liquidez del Mercado", icon: "💧", desc: "Las ondas buscan liquidez — domina los mapas", level: "amateur", unlockedBy: "7.4", locked: false },
  { id: 12, title: "Entrada Perfecta", icon: "🎯", desc: "Elliott + Fib + Liquidez = confluencia máxima", level: "experto", unlockedBy: "8.4", locked: false },
  { id: 13, title: "Escudo de Riesgo", icon: "🛡️", desc: "Stop, target, ratio R/B, tamaño de posición", level: "experto", unlockedBy: "9.5", locked: false },
  { id: 14, title: "Plan Maestro", icon: "📋", desc: "Análisis top-down + selección + timing completo", level: "experto", unlockedBy: "10.5", locked: false },
  { id: 15, title: "Trader Elliott", icon: "🏆", desc: "Operativa real con criterio propio — GRADUADO", level: "experto", unlockedBy: "11.4", locked: false },
];

const SESSIONS = [
  { date: "2026-03-15", duration: "~60 min", level: "principiante", completed: ["1.1","1.2","1.3","1.4","2.1","2.2","2.3","2.4","2.5","3.1","3.2"], notes: "Estructura, reglas y patrones básicos. Dificultad con R3 bajista — resuelta. Extensiones y truncamientos dominados." },
  { date: "2026-04-01", duration: "~90 min", level: "amateur", completed: ["3.3","3.4","3.5","4.1","4.2","4.3","4.4","4.5"], notes: "Diagonales completadas. M4 completo: Zigzag, Plana, Triángulo, Correcciones complejas, Alternancia. Examen Principiante: 10/10 ✅" },
  { date: "2026-04-05", duration: "~90 min", level: "amateur", completed: ["5.1","5.2","5.3","5.4"], notes: "M5 completo: Fibonacci avanzado. Retrocesos, extensiones, correcciones A-B-C, confluencia. Error recurrente en división de ratios — corregido." },
  { date: "2026-04-10", duration: "~120 min", level: "amateur", completed: ["6.1","6.2","6.3","6.4","6.5"], notes: "M6 completo: Protocolo timeframes, conteo BTC macro validado, conteo ETH O3 en curso ($8,516/$13,236 targets), errores comunes, conteos alternativos Plan A/B." },
  { date: "2026-04-15", duration: "~90 min", level: "amateur", completed: ["7.1","7.2","7.3","7.4"], notes: "M7 completo: Zonas de liquidación. Buy-side/sell-side, heatmaps, Elliott + liquidez. Examen Amateur: 9/10 ✅ — Error en P9 (plan B sin invalidación específica). Nivel Experto desbloqueado." },
  { date: "2026-05-09", duration: "~45 min", level: "experto", completed: ["8.1"], notes: "M8.1 dominado: Entradas en O3. Checklist de 3 confirmaciones (Fibonacci 50-61.8% + estructura ABC + R1 intacta). Ejercicio práctico con ETH: zona $2,440-$2,922, stop $880." },
  { date: "2026-05-14", duration: "~30 min", level: "experto", completed: ["8.2"], notes: "M8.2 dominado: Entradas en O5. 3 condiciones (O4 en 23.6-38.2% de O3 + volumen decreciente/divergencia + R/B mínimo 1:2). Invalidación ETH O5 = $4,963 (final O1, R3). Truncamiento como firma de agotamiento en O5. Concepto R/B explicado y aplicado." },
  { date: "2026-05-15", duration: "~45 min", level: "experto", completed: ["8.3","8.4"], notes: "M8 completo. 8.3: Entradas en ABC — dos momentos (onda A vs onda C), 3 condiciones para C, cálculo de R/B aplicado (ratio 1:9.5 en ejercicio BTC). 8.4: Confluencia Elliott+Fib+Liquidez — entrada A+ cuando las 3 capas coinciden. Pausa para consolidar fórmulas antes de M9." },
  { date: "2026-05-22", duration: "~60 min", level: "experto", completed: [], notes: "Sesión de consolidación de fórmulas. Las 5 fórmulas practicadas de memoria sin libreta: (1) % retroceso, (2) nivel de soporte, (3) target O3, (4) target C, (5) R/B. Todas dominadas con ejercicios progresivos. Listo para M9." },
  { date: "2026-05-23", duration: "~90 min", level: "experto", completed: ["9.1","9.2","9.3","9.4","9.5","10.1","10.2","10.3","10.4","10.5"], notes: "M9 completo: Stop loss por onda (R1/R3/ABC), take profit Fibonacci, ratio R/B (1:23 en ETH), tamaño de posición, invalidación y Plan A/B. M10 completo: Análisis top-down, selección de activo por R/B, timing con 3 confirmaciones, diario de operaciones, psicología del trader. Pilares 12, 13 y 14 desbloqueados. Documentos Pre-Análisis y Post-Análisis creados. Nivel Prop Trader (M12-M14) añadido al plan. Listo para M11 Operativa en Vivo." },
  { date: "2026-05-24", duration: "~120 min", level: "experto", completed: ["11.1"], notes: "M11.1 completo: Caso práctico BTC top-down completo. Mensual: ciclo nuevo validado $16,607→$126,398 (ATH confirmado), dos conteos alternativos válidos (Plan A O2=$16K / Plan B O2=$24K), invalidación total $16,607. Semanal: corrección ABC zigzag — A=$126,398→$80,500, B=$80,500→$98,160 (38% de A), C=$98,160→$60,171. Diario: nuevo impulso desde $60,171 — O1=$60,171→$76,013, O2=$76,013→$64,955 (69%), O3 en curso. 4H: ABC correctivo desde $83K, no impulso. Decisión: NO ENTRAR — 1/3 condiciones M8.1 (Fibonacci 69% fuera de rango, sin señal de reversión). R3 diario: $76,013. Nuevo concepto: velas OHLC mecha vs cuerpo, señales de reversión (martillo/engulfing/pin bar)." },
  { date: "2026-05-24", duration: "~90 min", level: "experto", completed: ["11.2"], notes: "M11.2 completo: Caso práctico ETH top-down completo. Mensual: O1=$80→$4,868 / O2=$4,868→$880 / O3 en curso → targets $8,627/$13,415 / invalidación $885. Semanal: O1s=$880→$4,963 / O2s=$4,963→$1,741 (ret 78%) / O3s en curso → targets $8,347/$12,430. Diario: O1d=$1,741→$2,460 / O2d=$2,460→$2,007 (ret 51%) / O3d pendiente. 4H: ABC completo en O2d. Decisión: ENTRAR — 3/3 condiciones M8.1. Plan: entrada=$2,092 / stop=$1,741 / T1=$3,170 (R/B 1:3.07) / T2=$3,889 (R/B 1:5.11)." },
  { date: "2026-05-30", duration: "~90 min", level: "experto", completed: ["11.3"], notes: "M11.3 completo: Caso práctico SOL (altcoin) top-down completo. Mensual: ciclo O1-O5 validado ($0.214→$295.11) — O5 extendida ($287 recorrido vs O3=$258), las 3 reglas respetadas, invalidación total $0.214. Semanal: corrección ABC post-ciclo — A=$295→$95 / B=$95→$253 (80% de A, plana) / C=$253→$67.70. Fibonacci O5: 50%=$151 / 61.8%=$118 / 78.6%=$69 — SOL en $82 entre 61.8% y 78.6%. Diario: estructura post-C lateral 3 meses. 4H: canal bajante de máximos decrecientes, sin impulso confirmado. Decisión: NO ENTRAR — 2/5 condiciones M8.1 (sin señal 4H, canal bajante activo). Invalidación: $67.70. Señal de entrada futura: ruptura canal + precio sobre $106." },
  { date: "2026-05-30", duration: "~60 min", level: "experto", completed: ["11.4"], notes: "M11.4 completo: Revisión y autocrítica de los 3 casos prácticos (BTC/ETH/SOL). Fortalezas: protocolo top-down consistente en los 3 activos, 60-70% de acierto en identificación de estructuras. Áreas de mejora: verificar R1/R2/R3 antes de enviar conteo, distinguir zigzag vs plana midiendo B primero. Hábito a desarrollar: más tiempo en gráfico para familiarizarse con estructuras en vivo." },
  { date: "2026-05-30", duration: "~45 min", level: "experto", completed: [], notes: "Examen Experto: APROBADO 8/10. P1 top-down ETH con ayuda parcial ✅. P2 plan completo números correctos ✅. P3 disciplina de stop perfecta ✅. P4 invalidaciones con corrección menor ($879→$880) ✅. P5 gestión en trade + pregunta inteligente sobre breakeven ✅. Errores menores: R/B redondeado 1:4 vs 1:4.3, estructura 4H descrita como corrección en lugar de impulso. Nivel Experto completado. Pilar 15 desbloqueado. Listo para M12 Prop Firms." },
];

const statusCfg = {
  completed: { label: "Dominado", color: "#10b981", bg: "#052e16", glow: "0 0 12px #10b98133", icon: "✅" },
  "in-progress": { label: "En progreso", color: "#f59e0b", bg: "#2a1f00", glow: "0 0 12px #f59e0b33", icon: "🔄" },
  locked: { label: "Bloqueado", color: "#444", bg: "#111", glow: "none", icon: "🔒" }
};

const levelCfg = {
  principiante: { color: "#10b981", bg: "#052e16", icon: "🌱" },
  amateur: { color: "#f59e0b", bg: "#2a1f00", icon: "⚡" },
  experto: { color: "#a855f7", bg: "#1a0a2e", icon: "🏆" },
  proptrader: { color: "#06b6d4", bg: "#021a1f", icon: "🎯" }
};

const tabs = [
  { id: "overview", label: "Vista General", icon: "📊" },
  { id: "principiante", label: "Principiante", icon: "🌱" },
  { id: "amateur", label: "Amateur", icon: "⚡" },
  { id: "experto", label: "Experto", icon: "🏆" },
  { id: "proptrader", label: "Prop Trader", icon: "🎯" },
  { id: "pillars", label: "Pilares", icon: "🏛️" },
  { id: "mistakes", label: "Errores", icon: "🔴" },
  { id: "exams", label: "Exámenes", icon: "📝" },
  { id: "cheatsheet", label: "Cheat Sheet", icon: "📋" },
];

function getAllConcepts() {
  return Object.values(LEVELS).flatMap(l => l.modules.flatMap(m => m.concepts));
}

function getLevelConcepts(levelId) {
  return LEVELS[levelId].modules.flatMap(m => m.concepts);
}

function getLevelProgress(levelId) {
  const concepts = getLevelConcepts(levelId);
  const done = concepts.filter(c => c.status === "completed").length;
  return { done, total: concepts.length, pct: Math.round((done / concepts.length) * 100) };
}

export default function ElliottAcademy() {
  const [tab, setTab] = useState("overview");
  const [selectedConcept, setSelectedConcept] = useState(null);
  const [expandedPillar, setExpandedPillar] = useState(null);
  const [showExam, setShowExam] = useState(null);
  const [revealedQ, setRevealedQ] = useState({});

  const all = getAllConcepts();
  const totalDone = all.filter(c => c.status === "completed").length;
  const totalAll = all.length;
  const globalPct = Math.round((totalDone / totalAll) * 100);
  const current = all.find(c => c.status === "in-progress");
  const currentLevel = current ? Object.keys(LEVELS).find(k => getLevelConcepts(k).find(c => c.id === current.id)) : null;

  const renderProgressBar = (pct, color, height = 8) => (
    <div style={{ width: "100%", height, background: "#1a1a2e", borderRadius: height / 2, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", borderRadius: height / 2, background: color, transition: "width 0.8s ease" }} />
    </div>
  );

  const renderLevelTab = (levelId) => {
    const level = LEVELS[levelId];
    const progress = getLevelProgress(levelId);
    const lcfg = levelCfg[levelId];
    const isLocked = levelId === "amateur" ? getLevelProgress("principiante").pct < 100 : levelId === "experto" ? getLevelProgress("amateur").pct < 100 : levelId === "proptrader" ? getLevelProgress("experto").pct < 100 : false;

    return (
      <div style={{ animation: "fadeUp 0.4s ease", opacity: isLocked ? 0.5 : 1 }}>
        {isLocked && (
          <div style={{ background: "#1a0a0f", border: "1px solid #3d1219", borderRadius: 12, padding: 16, marginBottom: 20, textAlign: "center" }}>
            <span style={{ fontSize: 24 }}>🔒</span>
            <div style={{ fontSize: 14, color: "#ef4444", fontWeight: 700, marginTop: 8 }}>Nivel bloqueado</div>
            <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>Completa el nivel anterior y aprueba su examen para desbloquear.</div>
          </div>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 8 }}>
          <span style={{ fontSize: 32 }}>{level.icon}</span>
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: 22, fontWeight: 900, color: "#f5f5f5", fontFamily: "'Inter', sans-serif" }}>Nivel {level.title}</h2>
            <p style={{ fontSize: 13, color: "#666", marginTop: 2 }}>{level.desc}</p>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 28, fontWeight: 800, color: lcfg.color, fontFamily: "'JetBrains Mono', monospace" }}>{progress.pct}%</div>
            <div style={{ fontSize: 11, color: "#666" }}>{progress.done}/{progress.total}</div>
          </div>
        </div>
        {renderProgressBar(progress.pct, lcfg.color, 10)}

        {progress.pct === 100 && (
          <div onClick={() => setShowExam(levelId)} style={{
            background: `linear-gradient(135deg, ${lcfg.bg}, #111)`, border: `1px solid ${lcfg.color}44`,
            borderRadius: 12, padding: 16, marginTop: 16, cursor: "pointer", textAlign: "center",
            animation: "glow 3s ease infinite"
          }}>
            <span style={{ fontSize: 20 }}>📝</span>
            <div style={{ fontSize: 14, fontWeight: 800, color: lcfg.color, marginTop: 6 }}>{level.examTitle} — ¡DISPONIBLE!</div>
            <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>Click para ver las preguntas del examen</div>
          </div>
        )}

        {level.modules.map(mod => (
          <div key={mod.id} style={{ marginTop: 28 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
              <span style={{ fontSize: 20 }}>{mod.icon}</span>
              <h3 style={{ fontSize: 15, fontWeight: 800, color: "#e5e5e5" }}>{mod.id}: {mod.title}</h3>
              <span style={{ fontSize: 11, color: "#555", background: "#111", padding: "2px 10px", borderRadius: 10, marginLeft: "auto", fontFamily: "'JetBrains Mono', monospace" }}>
                {mod.concepts.filter(c => c.status === "completed").length}/{mod.concepts.length}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {mod.concepts.map(concept => {
                const cfg = statusCfg[concept.status];
                return (
                  <div key={concept.id} style={{
                    background: "#0d0d14", border: `1px solid ${cfg.color}22`,
                    borderLeft: `4px solid ${cfg.color}`, borderRadius: 10, padding: "12px 16px",
                    display: "flex", alignItems: "center", gap: 14,
                    opacity: concept.status === "locked" ? 0.35 : 1, transition: "all 0.2s"
                  }}>
                    <span style={{ fontSize: 18, minWidth: 24 }}>{cfg.icon}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: "#e5e5e5" }}>{concept.title}</div>
                      <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>{concept.subtitle}</div>
                    </div>
                    <span style={{ fontSize: 12, color: "#444", fontFamily: "'JetBrains Mono', monospace" }}>{concept.id}</span>
                    {concept.date && <span style={{ fontSize: 11, color: "#444" }}>{concept.date}</span>}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div style={{ minHeight: "100vh", background: "#08080f", color: "#e5e5e5", fontFamily: "'Segoe UI', -apple-system, sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&family=Inter:wght@400;500;600;700;800;900&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #0a0a0f; }
        ::-webkit-scrollbar-thumb { background: #222; border-radius: 3px; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes glow { 0%,100% { box-shadow: 0 0 8px #f59e0b11; } 50% { box-shadow: 0 0 20px #f59e0b33; } }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.6; } }
        .thover:hover { background: #1a1a2e !important; }
      `}</style>

      {/* HEADER */}
      <div style={{ background: "linear-gradient(135deg, #0d0d1a, #111128, #0d0d1a)", borderBottom: "1px solid #1a1a2e", padding: "20px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 30 }}>🌊</span>
            <div>
              <h1 style={{ fontSize: 20, fontWeight: 900, color: "#f5f5f5", fontFamily: "'Inter', sans-serif", letterSpacing: -0.5 }}>Elliott Wave Academy</h1>
              <p style={{ fontSize: 12, color: "#555" }}>BTC & ETH • Plan BTC / Elliott Traders</p>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            {current && (
              <div style={{ background: "#1a1500", border: "1px solid #3d340066", borderRadius: 8, padding: "6px 14px", animation: "pulse 3s infinite" }}>
                <span style={{ fontSize: 11, color: "#f59e0b", fontWeight: 700 }}>🔄 {current.id} — {current.title}</span>
              </div>
            )}
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#f59e0b", fontFamily: "'JetBrains Mono', monospace" }}>{globalPct}%</div>
              <div style={{ fontSize: 10, color: "#555" }}>{totalDone}/{totalAll} conceptos</div>
            </div>
          </div>
        </div>
      </div>

      {/* TABS */}
      <div style={{ display: "flex", gap: 1, padding: "8px 24px 0", overflowX: "auto", borderBottom: "1px solid #1a1a2e", background: "#0a0a12" }}>
        {tabs.map(t => (
          <button key={t.id} className="thover" onClick={() => { setTab(t.id); setShowExam(null); }}
            style={{
              background: tab === t.id ? "#1a1a2e" : "transparent",
              border: "none", borderBottom: tab === t.id ? "2px solid #f59e0b" : "2px solid transparent",
              color: tab === t.id ? "#f59e0b" : "#555", padding: "8px 14px", cursor: "pointer",
              fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", borderRadius: "6px 6px 0 0"
            }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* CONTENT */}
      <div style={{ padding: "24px", maxWidth: 880, margin: "0 auto" }}>

        {/* OVERVIEW */}
        {tab === "overview" && (
          <div style={{ animation: "fadeUp 0.4s ease" }}>
            {/* Level Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14, marginBottom: 28 }}>
              {Object.entries(LEVELS).map(([key, level]) => {
                const prog = getLevelProgress(key);
                const lcfg = levelCfg[key];
                const isActive = currentLevel === key;
                return (
                  <div key={key} onClick={() => setTab(key)} style={{
                    background: isActive ? `linear-gradient(135deg, ${lcfg.bg}, #0d0d14)` : "#0d0d14",
                    border: `1px solid ${isActive ? lcfg.color + "44" : "#1a1a2e"}`,
                    borderRadius: 14, padding: 20, cursor: "pointer", transition: "all 0.3s",
                    borderTop: `3px solid ${lcfg.color}`
                  }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 24 }}>{level.icon}</span>
                        <span style={{ fontSize: 16, fontWeight: 800, color: "#f5f5f5" }}>{level.title}</span>
                      </div>
                      <span style={{ fontSize: 20, fontWeight: 800, color: lcfg.color, fontFamily: "'JetBrains Mono', monospace" }}>{prog.pct}%</span>
                    </div>
                    {renderProgressBar(prog.pct, lcfg.color)}
                    <div style={{ fontSize: 12, color: "#555", marginTop: 8 }}>{prog.done}/{prog.total} conceptos • {level.modules.length} módulos</div>
                    {isActive && <div style={{ fontSize: 11, color: lcfg.color, marginTop: 8, fontWeight: 700 }}>← NIVEL ACTUAL</div>}
                  </div>
                );
              })}
            </div>

            {/* Stats */}
            <div style={{ display: "flex", gap: 10, marginBottom: 24, flexWrap: "wrap" }}>
              {[
                { icon: "✅", val: totalDone, label: "Dominados" },
                { icon: "📐", val: totalAll, label: "Total" },
                { icon: "🏛️", val: PILLARS.filter(p => !p.locked).length + "/" + PILLARS.length, label: "Pilares" },
                { icon: "🔴", val: MISTAKES.length, label: "Errores→Lecciones" },
                { icon: "📅", val: SESSIONS.length, label: "Sesiones" },
              ].map((s, i) => (
                <div key={i} style={{
                  background: "#0d0d14", border: "1px solid #1a1a2e", borderRadius: 10,
                  padding: "12px 16px", display: "flex", alignItems: "center", gap: 10, flex: "1 1 120px"
                }}>
                  <span style={{ fontSize: 22 }}>{s.icon}</span>
                  <div>
                    <div style={{ fontSize: 18, fontWeight: 800, color: "#e5e5e5", fontFamily: "'JetBrains Mono'" }}>{s.val}</div>
                    <div style={{ fontSize: 10, color: "#555" }}>{s.label}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Recent Session */}
            {SESSIONS.length > 0 && (
              <div style={{ background: "#0d0d14", border: "1px solid #1a1a2e", borderRadius: 14, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: "#888", marginBottom: 12 }}>📅 ÚLTIMA SESIÓN — {SESSIONS[SESSIONS.length - 1].date}</div>
                <div style={{ fontSize: 13, color: "#aaa", lineHeight: 1.7 }}>{SESSIONS[SESSIONS.length - 1].notes}</div>
              </div>
            )}
          </div>
        )}

        {/* LEVEL TABS */}
        {tab === "principiante" && renderLevelTab("principiante")}
        {tab === "amateur" && renderLevelTab("amateur")}
        {tab === "experto" && renderLevelTab("experto")}
        {tab === "proptrader" && renderLevelTab("proptrader")}

        {/* PILLARS */}
        {tab === "pillars" && (
          <div style={{ animation: "fadeUp 0.4s ease" }}>
            <div style={{ marginBottom: 20 }}>
              <h2 style={{ fontSize: 20, fontWeight: 900, color: "#f5f5f5", marginBottom: 4 }}>🏛️ Pilares del Conocimiento</h2>
              <p style={{ fontSize: 12, color: "#555" }}>Se desbloquean al dominar conceptos. Tu colección de verdades del mercado.</p>
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                {Object.entries(levelCfg).map(([k, v]) => (
                  <span key={k} style={{ fontSize: 11, color: v.color, background: v.bg, padding: "3px 10px", borderRadius: 8 }}>
                    {v.icon} {k}: {PILLARS.filter(p => p.level === k && !p.locked).length}/{PILLARS.filter(p => p.level === k).length}
                  </span>
                ))}
              </div>
            </div>
            {["principiante", "amateur", "experto"].map(level => (
              <div key={level} style={{ marginBottom: 24 }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: levelCfg[level].color, marginBottom: 10, letterSpacing: 1 }}>
                  {levelCfg[level].icon} {level.toUpperCase()}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {PILLARS.filter(p => p.level === level).map(p => (
                    <div key={p.id} onClick={() => !p.locked && setExpandedPillar(expandedPillar === p.id ? null : p.id)}
                      style={{
                        background: p.locked ? "#0a0a0f" : expandedPillar === p.id ? "#12121f" : "#0d0d14",
                        border: `1px solid ${p.locked ? "#151515" : expandedPillar === p.id ? "#f59e0b44" : "#1a1a2e"}`,
                        borderLeft: `4px solid ${p.locked ? "#222" : levelCfg[level].color}`,
                        borderRadius: 12, padding: 16, cursor: p.locked ? "default" : "pointer",
                        opacity: p.locked ? 0.3 : 1, transition: "all 0.3s"
                      }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <span style={{ fontSize: 28, filter: p.locked ? "grayscale(1)" : "none" }}>{p.icon}</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 14, fontWeight: 800, color: p.locked ? "#333" : "#e5e5e5" }}>{p.title}</div>
                          <div style={{ fontSize: 12, color: p.locked ? "#222" : "#777", marginTop: 2 }}>{p.desc}</div>
                        </div>
                        {p.locked ? (
                          <span style={{ fontSize: 10, color: "#333", background: "#111", padding: "2px 8px", borderRadius: 6 }}>🔒 {p.unlockedBy}</span>
                        ) : (
                          <span style={{ fontSize: 10, color: "#10b981", background: "#052e16", padding: "2px 8px", borderRadius: 6 }}>✅</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* MISTAKES */}
        {tab === "mistakes" && (
          <div style={{ animation: "fadeUp 0.4s ease" }}>
            <h2 style={{ fontSize: 20, fontWeight: 900, color: "#f5f5f5", marginBottom: 4 }}>🔴 Diario de Errores → Lecciones</h2>
            <p style={{ fontSize: 12, color: "#555", marginBottom: 20 }}>Cada error te hace más fuerte. Revísalos antes de cada sesión.</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {MISTAKES.map(m => (
                <div key={m.id} style={{
                  background: "#0d0d14", border: "1px solid #1a1a2e", borderRadius: 10,
                  padding: 16, borderLeft: "4px solid #ef4444"
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontSize: 10, color: "#ef4444", fontWeight: 700, background: "#1a0a0f", padding: "2px 8px", borderRadius: 8 }}>Concepto {m.concept}</span>
                    <span style={{ fontSize: 10, color: "#444", fontFamily: "'JetBrains Mono'" }}>{m.date}</span>
                  </div>
                  <div style={{ fontSize: 13, color: "#e5a0a0", marginBottom: 6 }}>❌ {m.error}</div>
                  <div style={{ fontSize: 13, color: "#10b981", background: "#10b98108", padding: "8px 12px", borderRadius: 6 }}>✅ {m.lesson}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* EXAMS */}
        {tab === "exams" && (
          <div style={{ animation: "fadeUp 0.4s ease" }}>
            <h2 style={{ fontSize: 20, fontWeight: 900, color: "#f5f5f5", marginBottom: 4 }}>📝 Centro de Exámenes</h2>
            <p style={{ fontSize: 12, color: "#555", marginBottom: 20 }}>Aprueba cada examen para avanzar al siguiente nivel. Las preguntas se revelan al hacer click.</p>
            {Object.entries(LEVELS).map(([key, level]) => {
              const prog = getLevelProgress(key);
              const available = prog.pct === 100;
              const lcfg = levelCfg[key];
              const isOpen = showExam === key;
              return (
                <div key={key} style={{
                  background: "#0d0d14", border: `1px solid ${isOpen ? lcfg.color + "44" : "#1a1a2e"}`,
                  borderRadius: 14, padding: 20, marginBottom: 16,
                  borderTop: `3px solid ${available ? lcfg.color : "#222"}`,
                  opacity: available ? 1 : 0.4
                }}>
                  <div onClick={() => available && setShowExam(isOpen ? null : key)}
                    style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: available ? "pointer" : "default" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 24 }}>{level.icon}</span>
                      <div>
                        <div style={{ fontSize: 15, fontWeight: 800, color: "#e5e5e5" }}>{level.examTitle}</div>
                        <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>{level.examDesc}</div>
                      </div>
                    </div>
                    <span style={{
                      fontSize: 11, fontWeight: 700, padding: "4px 12px", borderRadius: 8,
                      color: available ? lcfg.color : "#444",
                      background: available ? lcfg.bg : "#111"
                    }}>
                      {available ? "✅ DISPONIBLE" : `🔒 ${prog.pct}% completado`}
                    </span>
                  </div>
                  {isOpen && (
                    <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid #1a1a2e", animation: "fadeUp 0.3s ease" }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#888", marginBottom: 12 }}>{level.exam.length} PREGUNTAS — Click en cada una para revelarla</div>
                      {level.exam.map((e, i) => (
                        <div key={i} onClick={() => setRevealedQ(prev => ({ ...prev, [`${key}-${i}`]: !prev[`${key}-${i}`] }))}
                          style={{
                            background: revealedQ[`${key}-${i}`] ? "#111118" : "#0a0a10",
                            border: "1px solid #1a1a2e", borderRadius: 8, padding: "12px 16px",
                            marginBottom: 8, cursor: "pointer", transition: "all 0.2s"
                          }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <span style={{
                              fontSize: 12, fontWeight: 700, color: lcfg.color, background: lcfg.bg,
                              width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center",
                              justifyContent: "center", flexShrink: 0
                            }}>{i + 1}</span>
                            <div style={{ flex: 1 }}>
                              {revealedQ[`${key}-${i}`] ? (
                                <div style={{ fontSize: 13, color: "#e5e5e5", lineHeight: 1.6 }}>{e.q}</div>
                              ) : (
                                <div style={{ fontSize: 13, color: "#444" }}>Click para revelar pregunta #{i + 1}</div>
                              )}
                            </div>
                            <span style={{ fontSize: 10, color: "#444", background: "#111", padding: "2px 8px", borderRadius: 6 }}>{e.type}</span>
                          </div>
                        </div>
                      ))}
                      <div style={{
                        marginTop: 14, background: "#1a1500", border: "1px solid #3d3400",
                        borderRadius: 8, padding: 12, textAlign: "center"
                      }}>
                        <div style={{ fontSize: 12, color: "#f59e0b" }}>💡 Para tomar el examen, pídele a Claude que te lo aplique en el chat.</div>
                        <div style={{ fontSize: 11, color: "#888", marginTop: 4 }}>Di: "Quiero tomar el examen de {level.title.toLowerCase()}"</div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* CHEAT SHEET */}
        {tab === "cheatsheet" && (
          <div style={{ animation: "fadeUp 0.4s ease" }}>
            <h2 style={{ fontSize: 20, fontWeight: 900, color: "#f5f5f5", marginBottom: 20 }}>📋 Cheat Sheet — Referencia Rápida</h2>

            <div style={{ background: "#0d0d14", border: "1px solid #1a1a2e", borderRadius: 14, padding: 20, marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 800, color: "#e5e5e5", marginBottom: 14 }}>🏗️ Estructura</h3>
              <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 12, color: "#888", background: "#0a0a10", padding: 16, borderRadius: 8, lineHeight: 1.8, whiteSpace: "pre", border: "1px solid #151520" }}>
{`Impulso  = 5 ondas (O1↑ O2↓ O3↑ O4↓ O5↑)
Corrección = 3 ondas (A↓ B↑ C↓)
Ciclo    = 5 + 3 = 8 ondas

⚠️ Estructura define tipo, NO dirección`}
              </div>
            </div>

            <div style={{ background: "#0d0d14", border: "1px solid #1a1a2e", borderRadius: 14, padding: 20, marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 800, color: "#e5e5e5", marginBottom: 14 }}>⚔️ Reglas Inviolables</h3>
              {[
                { id: "R1", r: "O2 no pasa inicio O1", a: "No MENOR que inicio O1", b: "No MAYOR que inicio O1" },
                { id: "R2", r: "O3 nunca la más corta", a: "Aplica igual", b: "Aplica igual" },
                { id: "R3", r: "O4 no entra en rango O1", a: "No MENOR que final O1", b: "No MAYOR que final O1" },
              ].map(r => (
                <div key={r.id} style={{ background: "#111118", borderRadius: 8, padding: 14, marginBottom: 8, border: "1px solid #1a1a2e" }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#f59e0b", marginBottom: 8 }}>{r.id}: {r.r}</div>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <div style={{ flex: 1, minWidth: 140, background: "#10b98108", padding: "6px 10px", borderRadius: 6, border: "1px solid #10b98122" }}>
                      <div style={{ fontSize: 10, color: "#10b981", fontWeight: 700 }}>📈 ALCISTA</div>
                      <div style={{ fontSize: 11, color: "#ccc", marginTop: 3 }}>{r.a}</div>
                    </div>
                    <div style={{ flex: 1, minWidth: 140, background: "#ef444408", padding: "6px 10px", borderRadius: 6, border: "1px solid #ef444422" }}>
                      <div style={{ fontSize: 10, color: "#ef4444", fontWeight: 700 }}>📉 BAJISTA</div>
                      <div style={{ fontSize: 11, color: "#ccc", marginTop: 3 }}>{r.b}</div>
                    </div>
                  </div>
                </div>
              ))}
              <div style={{ background: "#1a1500", border: "1px solid #3d3400", borderRadius: 8, padding: 12, marginTop: 10 }}>
                <div style={{ fontSize: 10, fontWeight: 800, color: "#f59e0b", letterSpacing: 1, marginBottom: 4 }}>🔑 REGLA UNIVERSAL</div>
                <div style={{ fontSize: 12, color: "#e5e5e5", lineHeight: 1.7 }}>
                  Alcista → no puede ser MENOR • Bajista → no puede ser MAYOR<br />
                  <span style={{ color: "#777" }}>R1=INICIO O1 | R3=FINAL O1</span>
                </div>
              </div>
            </div>

            <div style={{ background: "#0d0d14", border: "1px solid #1a1a2e", borderRadius: 14, padding: 20 }}>
              <h3 style={{ fontSize: 15, fontWeight: 800, color: "#e5e5e5", marginBottom: 14 }}>📊 Patrones</h3>
              {[
                { t: "📏 Extensiones", items: ["Una onda se estira mucho más", "O3 más común en BTC", "Solo UNA por impulso", "O3 ext → O1 ≈ O5"] },
                { t: "⚡ Truncamientos", items: ["O5 no supera extremo O3", "Alcista: O5 < máx O3 | Bajista: O5 > mín O3", "Solo válido si O3 fue extensión", "Corrección agresiva viene después", "≠ cambio de tendencia automático"] },
                { t: "📐 Diagonales", items: ["Cuña con líneas convergentes", "Inicial→O1 | Final→O5", "O5 diagonal final → reversión fuerte", "O4 SÍ puede solaparse con O1"] },
              ].map(p => (
                <div key={p.t} style={{ background: "#111118", borderRadius: 8, padding: 14, marginBottom: 8, border: "1px solid #1a1a2e" }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#f59e0b", marginBottom: 8 }}>{p.t}</div>
                  {p.items.map((item, i) => (
                    <div key={i} style={{ fontSize: 11, color: "#bbb", paddingLeft: 10, borderLeft: "2px solid #1a1a2e", padding: "2px 10px", marginBottom: 3 }}>• {item}</div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
