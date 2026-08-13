//+------------------------------------------------------------------+
//|          Q7_SignalCatcher.mq5  |
//|                         Monitoriza posiciones de cualquier EA     |
//|                    y las convierte en senales OPEN_LONG/SHORT     |
//+------------------------------------------------------------------+
#property copyright "Q7"
#property version   "1.0"
#property description "Catcher universal: convierte trades de cualquier EA en señales Q7"

//--- inputs
input group "=== CATcher ==="
input string   InpSymbolWatch      = "USTEC";   // Simbolo a vigilar (vacio = todos)
input bool     InpShowLog          = true;      // Mostrar log en el diario

//--- globals
struct PositionSnapshot
{
   ulong    ticket;
   string   symbol;
   int      direction;   // 1=LONG, -1=SHORT
   double   volume;
   double   price;
};

PositionSnapshot g_snapshot[];
int             g_snapshotCount = 0;
int             g_signalCount = 0;
bool            g_firstRun = true;

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpShowLog)
      Print("Q7 Catcher: Watching Symbol=", InpSymbolWatch);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   // Heartbeat cada 30s
   static datetime lastHb = 0;
   if(TimeCurrent() - lastHb >= 30)
   {
      // Write heartbeat silently (engine detection, no log spam)
      PostHeartbeat();
      lastHb = TimeCurrent();
   }

   // Skip first run to let positions settle
   if(g_firstRun)
   {
      TakeSnapshot();
      g_firstRun = false;
      return;
   }

   // Build current snapshot
   PositionSnapshot current[];
   int currentCount = 0;
   ArrayResize(current, 50);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;

      string symbol = PositionGetString(POSITION_SYMBOL);

      // Filter by symbol only (no magic filter - catches all)
      if(InpSymbolWatch != "" && symbol != InpSymbolWatch) continue;

      ArrayResize(current, currentCount + 1);
      current[currentCount].ticket    = ticket;
      current[currentCount].symbol    = symbol;
      current[currentCount].direction = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      current[currentCount].volume    = PositionGetDouble(POSITION_VOLUME);
      current[currentCount].price     = PositionGetDouble(POSITION_PRICE_OPEN);
      currentCount++;
   }

   // Compare with previous snapshot → find NEW positions
   for(int i = 0; i < currentCount; i++)
   {
      bool found = false;
      for(int j = 0; j < g_snapshotCount; j++)
      {
         if(current[i].ticket == g_snapshot[j].ticket)
         {
            found = true;
            break;
         }
      }

      if(!found)
      {
         // NEW position detected!
         int dir = current[i].direction;
         string symbolName = current[i].symbol;
         double vol = current[i].volume;

         WriteSignal(dir, symbolName, vol);
      }
   }

   // Save current as new snapshot
   ArrayResize(g_snapshot, currentCount);
   for(int i = 0; i < currentCount; i++)
      g_snapshot[i] = current[i];
   g_snapshotCount = currentCount;
}

//+------------------------------------------------------------------+
//| Heartbeat silencioso (sin spam en el log)                         |
//+------------------------------------------------------------------+
void PostHeartbeat()
{
   string json = "{\"type\":\"HEARTBEAT\",\"direction\":0,\"atr\":0,\"instrument\":\"" + InpSymbolWatch + "\"}";
   string fileName = "Q7\\signals\\heartbeat_catcher.json";
   int handle = FileOpen(fileName, FILE_WRITE|FILE_TXT);
   if(handle != INVALID_HANDLE)
   {
      FileWriteString(handle, json);
      FileClose(handle);
   }
}

//+------------------------------------------------------------------+
//| Write signal to Q7 signals folder                                 |
//+------------------------------------------------------------------+
void WriteSignal(int direction, string symbol, double volume)
{
   string typeStr = (direction == 1) ? "OPEN_LONG" : "OPEN_SHORT";
   string json = "{";
   json += "\"type\":\"" + typeStr + "\",";
   json += "\"instrument\":\"" + symbol + "\",";
   json += "\"volume\":" + DoubleToString(volume, 2);
   json += "}";

   string fileName = "Q7\\signals\\cyclescale_catcher_" + IntegerToString(g_signalCount) + ".json";
   int handle = FileOpen(fileName, FILE_WRITE|FILE_TXT);
   if(handle != INVALID_HANDLE)
   {
      FileWriteString(handle, json);
      FileClose(handle);
      g_signalCount++;

      if(InpShowLog)
      {
         string dirStr = (direction == 1) ? "LONG" : "SHORT";
         Print("Q7 Catcher: ", dirStr, " ", symbol, " vol=", DoubleToString(volume,2), " → signal #", g_signalCount);
      }
   }
   else
   {
      if(InpShowLog)
         Print("Q7 Catcher: ERR file ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Take initial snapshot (skip first run signals)                    |
//+------------------------------------------------------------------+
void TakeSnapshot()
{
   ArrayResize(g_snapshot, 50);
   g_snapshotCount = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;

      string symbol = PositionGetString(POSITION_SYMBOL);

      if(InpSymbolWatch != "" && symbol != InpSymbolWatch) continue;

      ArrayResize(g_snapshot, g_snapshotCount + 1);
      g_snapshot[g_snapshotCount].ticket    = ticket;
      g_snapshot[g_snapshotCount].symbol    = symbol;
      g_snapshot[g_snapshotCount].direction = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      g_snapshot[g_snapshotCount].volume    = PositionGetDouble(POSITION_VOLUME);
      g_snapshot[g_snapshotCount].price     = PositionGetDouble(POSITION_PRICE_OPEN);
      g_snapshotCount++;
   }

   if(InpShowLog)
      Print("Q7 Catcher: Initial snapshot = ", g_snapshotCount, " positions");
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(InpShowLog)
      Print("Q7 Catcher: Total signals = ", g_signalCount);
}
//+------------------------------------------------------------------+
