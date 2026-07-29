# Análisis de Bots Originales (MT5)

## Archivos Disponibles

### EAs Compilados (.ex5)

| Archivo | Descripción | Versión Estimada |
|---------|-------------|-----------------|
| `ALG Funded.ex5` | ALG Funded EA | v1.5.6 |
| `GYR EA.ex5` | GYR EA | Desconocida |
| `GYR.ex5` | GYR (variante) | Desconocida |
| `Bfunded/BFunded - EA.ex5` | BFunded EA | v1.0 |
| `Bfunded/BFunded - EA.2.0.ex5` | BFunded EA | v2.0 |
| `Bfunded/ALG Funded.ex5` | ALG Funded (copia) | v1.5.6 |
| `Bfunded/ALG Funded 2.0.ex5` | ALG Funded Plus | v2.0 |

### Sets de Parámetros (.set)

| Archivo | EA | Instrumento | Timeframe |
|---------|-----|-------------|-----------|
| `gyroro.set` | GYR EA | XAUUSD (Oro) | ? |
| `gyrus30.set` | GYR EA | US30 | ? |
| `Bfunded/us30.set` | BFunded EA | US30 | ? |
| `Bfunded/us30 5m.set` | BFunded EA | US30 | M5 |
| `Bfunded/us30 M1-P19-1.8-2 4400.set` | BFunded EA 2.0 | US30 | M1 |
| `Bfunded/ALGFundedus30.set` | ALG Funded | US30 | M5 |
| `Bfunded/xauusd 5m.set` | BFunded EA | XAUUSD | M5 |
| `Bfunded/gbpusd 5 min optimizado.set` | BFunded EA | GBPUSD | M5 |

### Otros Archivos

| Archivo | Contenido |
|---------|-----------|
| `Bfunded/cuentas BeFunded.txt` | Credenciales demo + API endpoint |

## API Detectada

Se encontró una URL de API en los archivos:
```
https://api-production-c406.up.railway.app/
```

Esto sugiere que los EAs pueden estar comunicándose con un servidor externo para:
- Validación de licencia
- Señales de trading remotas
- Sincronización de parámetros
- Registro de operaciones

**IMPORTANTE**: Este endpoint debe ser analizado para entender si la lógica de trading está en el EA o en el servidor.

## Sobre los Archivos .ex5

Los archivos `.ex5` son binarios compilados de MQL5. Opciones para extraer la lógica:

1. **Decompilación directa**: Herramientas de terceros (resultados variables, puede ser código ofuscado)
2. **Análisis de comportamiento**: Ejecutar en MT5 demo y observar entradas/salidas
3. **Ingeniería inversa por parámetros**: Deducir lógica desde los archivos .set

## Prioridad de Análisis

1. BFunded EA - Más sets disponibles, mejor documentado en parámetros
2. ALG Funded - Similar estructura, variante del anterior
3. GYR EA - Menos información disponible
