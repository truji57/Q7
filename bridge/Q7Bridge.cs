// Q7Bridge.cs
// NinjaTrader 8 AddOn - TCP Socket Bridge
// Protocolo: TCP JSON newline-delimited
// NO requiere dependencias externas (usa System.Web.Script.Serialization)

#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.AddOns;
#endregion

namespace NinjaTrader.NinjaScript.AddOns.Q7
{
    public class Q7Bridge : AddOnBase
    {
        private TcpListener tcpListener;
        private Thread listenerThread;
        private ConcurrentDictionary<string, TcpClient> clients = new ConcurrentDictionary<string, TcpClient>();
        private CancellationTokenSource cts;
        private string signalOutputPath;
        private JavaScriptSerializer json = new JavaScriptSerializer();

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "Q7Bridge";
            }
            else if (State == State.Configure)
            {
                string docsPath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "NinjaTrader 8"
                );

                signalOutputPath = Path.Combine(docsPath, "Q7", "signals");
                if (!Directory.Exists(signalOutputPath))
                    Directory.CreateDirectory(signalOutputPath);
            }
            else if (State == State.Active)
            {
                StartServer();
            }
            else if (State == State.Terminated)
            {
                StopServer();
            }
        }

        private void StartServer()
        {
            cts = new CancellationTokenSource();
            int port = LoadPortFromConfig();

            try
            {
                tcpListener = new TcpListener(IPAddress.Loopback, port);
                tcpListener.Start();

                listenerThread = new Thread(() => AcceptClients(cts.Token))
                {
                    IsBackground = true,
                    Name = "Q7Bridge-Listener"
                };
                listenerThread.Start();

                Print("Q7: TCP ready on :" + port);
            }
            catch (Exception ex)
            {
                Print("Q7Bridge: Failed to start on port " + port + ": " + ex.Message);
            }
        }

        private int LoadPortFromConfig()
        {
            string configPath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "NinjaTrader 8", "q7_config.json"
            );

            if (File.Exists(configPath))
            {
                try
                {
                    string content = File.ReadAllText(configPath);
                    var cfg = json.Deserialize<Dictionary<string, object>>(content);
                    if (cfg != null && cfg.ContainsKey("port"))
                        return Convert.ToInt32(cfg["port"]);
                }
                catch { }
            }
            return 5556;
        }

        private void AcceptClients(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    if (tcpListener.Pending())
                    {
                        TcpClient client = tcpListener.AcceptTcpClient();
                        string id = Guid.NewGuid().ToString("N");

                        clients[id] = client;

                        Thread clientThread = new Thread(() => HandleClient(id, client, token))
                        {
                            IsBackground = true,
                            Name = "Q7Bridge-Client"
                        };
                        clientThread.Start();

                        Print("Q7Bridge: Client connected [" + id + "]");
                    }
                    Thread.Sleep(100);
                }
                catch (Exception ex)
                {
                    if (!token.IsCancellationRequested)
                        Print("Q7Bridge: Accept error: " + ex.Message);
                }
            }
        }

        private void HandleClient(string clientId, TcpClient client, CancellationToken token)
        {
            try
            {
                NetworkStream stream = client.GetStream();
                StreamReader reader = new StreamReader(stream, Encoding.UTF8);
                StreamWriter writer = new StreamWriter(stream, Encoding.UTF8);
                writer.AutoFlush = true;

                while (!token.IsCancellationRequested && client.Connected)
                {
                    string line = reader.ReadLine();
                    if (line == null) break;

                    string response = ProcessCommand(line);
                    writer.WriteLine(response);
                }
            }
            catch (Exception ex)
            {
                Print("Q7Bridge: Client error: " + ex.Message);
            }
            finally
            {
                TcpClient removed;
                clients.TryRemove(clientId, out removed);
                Print("Q7Bridge: Client disconnected [" + clientId + "]");
            }
        }

        private string ProcessCommand(string rawJson)
        {
            try
            {
                var cmd = json.Deserialize<Dictionary<string, object>>(rawJson);
                if (cmd == null) return Error("Invalid JSON");

                string action = GetString(cmd, "action", "").ToUpper();

                switch (action)
                {
                    case "STATUS": return GetStatus();
                    case "OPEN": return ExecuteOpen(cmd);
                    case "CLOSE": return ExecuteClose(cmd);
                    case "CLOSE_ALL": return CloseAll(cmd);
                    case "SIGNAL": return ForwardSignal(cmd);
                    case "PING": return OkObj(new { data = "pong" });
                    default: return Error("Unknown action: " + action);
                }
            }
            catch (Exception ex)
            {
                return Error("Parse error: " + ex.Message);
            }
        }

        private string GetStatus()
        {
            var accountList = new List<Dictionary<string, object>>();

            lock (Account.All)
            {
                foreach (Account acct in Account.All)
                {
                    try
                    {
                        double cash = acct.Get(AccountItem.CashValue, Currency.UsDollar);
                        double realized = acct.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar);
                        double unrealized = acct.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar);

                        var positionList = new List<Dictionary<string, object>>();
                        foreach (var pos in acct.Positions)
                        {
                            positionList.Add(new Dictionary<string, object>
                            {
                                ["instrument"] = pos.Instrument != null ? pos.Instrument.FullName : "",
                                ["direction"] = pos.MarketPosition == MarketPosition.Long ? "LONG" : "SHORT",
                                ["quantity"] = pos.Quantity,
                                ["avg_price"] = pos.AveragePrice,
                                ["unrealized_pnl"] = pos.GetUnrealizedProfitLoss(PerformanceUnit.Currency, 0)
                            });
                        }

                        accountList.Add(new Dictionary<string, object>
                        {
                            ["name"] = acct.Name,
                            ["balance"] = cash,
                            ["realized_pnl"] = realized,
                            ["unrealized_pnl"] = unrealized,
                            ["total_pnl"] = realized + unrealized,
                            ["positions"] = positionList
                        });
                    }
                    catch { }
                }
            }

            return OkObj(new { accounts = accountList });
        }

        private string ExecuteOpen(Dictionary<string, object> cmd)
        {
            string accountName = GetString(cmd, "account", "");
            string instrument = GetString(cmd, "instrument", "YM 09-26");
            string direction = GetString(cmd, "direction", "LONG").ToUpper();
            int contracts = GetInt(cmd, "contracts", 1);

            Account acct = FindAccount(accountName);
            if (acct == null) return Error("Account not found: " + accountName);

            Instrument inst = Instrument.GetInstrument(instrument);
            if (inst == null) return Error("Instrument not found: " + instrument);

            OrderAction orderAction = direction == "LONG" ? OrderAction.Buy : OrderAction.SellShort;

            try
            {
                Order entryOrder = acct.CreateOrder(inst, orderAction, OrderType.Market,
                    TimeInForce.Day, contracts, 0, 0, "", "", null);

                string positionId = Guid.NewGuid().ToString("N").Substring(0, 16);
                return OkObj(new { position_id = positionId, status = "SUBMITTED" });
            }
            catch (Exception ex)
            {
                return Error("Order failed: " + ex.Message);
            }
        }

        private string ExecuteClose(Dictionary<string, object> cmd)
        {
            string accountName = GetString(cmd, "account", "");
            string instrument = GetString(cmd, "instrument", "");

            Account acct = FindAccount(accountName);
            if (acct == null) return Error("Account not found: " + accountName);

            int closed = 0;
            foreach (var pos in acct.Positions)
            {
                if (!string.IsNullOrEmpty(instrument) && pos.Instrument != null
                    && !string.Equals(pos.Instrument.FullName, instrument, StringComparison.OrdinalIgnoreCase))
                    continue;

                OrderAction closeAction = pos.MarketPosition == MarketPosition.Long
                    ? OrderAction.Sell
                    : OrderAction.BuyToCover;

                acct.CreateOrder(pos.Instrument, closeAction, OrderType.Market,
                    TimeInForce.Day, pos.Quantity, 0, 0, "", "", null);
                closed++;
            }

            return OkObj(new { closed_positions = closed });
        }

        private string CloseAll(Dictionary<string, object> cmd)
        {
            string accountName = GetString(cmd, "account", "");
            Account acct = FindAccount(accountName);
            if (acct == null) return Error("Account not found: " + accountName);

            int closed = 0;
            foreach (var pos in acct.Positions)
            {
                OrderAction closeAction = pos.MarketPosition == MarketPosition.Long
                    ? OrderAction.Sell
                    : OrderAction.BuyToCover;
                acct.CreateOrder(pos.Instrument, closeAction, OrderType.Market,
                    TimeInForce.Day, pos.Quantity, 0, 0, "", "", null);
                closed++;
            }

            return OkObj(new { closed_positions = closed });
        }

        private string ForwardSignal(Dictionary<string, object> cmd)
        {
            string fileName = "signal_" + DateTime.Now.ToString("yyyyMMdd_HHmmssfff") + ".json";
            string filePath = Path.Combine(signalOutputPath, fileName);
            File.WriteAllText(filePath, json.Serialize(cmd));
            Print("Q7Bridge: Signal forwarded -> " + fileName);
            return OkObj(new { forwarded = true, file = fileName });
        }

        private Account FindAccount(string name)
        {
            lock (Account.All)
            {
                foreach (Account a in Account.All)
                {
                    if (string.Equals(a.Name, name, StringComparison.OrdinalIgnoreCase))
                        return a;
                }
            }
            return null;
        }

        private string Ok(object data)
        {
            if (data is string)
                return (string)data;

            var result = new Dictionary<string, object>
            {
                ["success"] = true,
                ["data"] = data
            };
            return json.Serialize(result);
        }

        private string OkObj(object data)
        {
            var result = new Dictionary<string, object>
            {
                ["success"] = true,
                ["data"] = data
            };
            return json.Serialize(result);
        }

        private string Error(string message)
        {
            var result = new Dictionary<string, object>
            {
                ["success"] = false,
                ["error"] = message
            };
            return json.Serialize(result);
        }

        private string GetString(Dictionary<string, object> dict, string key, string defaultValue)
        {
            if (dict.ContainsKey(key) && dict[key] != null)
                return dict[key].ToString();
            return defaultValue;
        }

        private int GetInt(Dictionary<string, object> dict, string key, int defaultValue)
        {
            if (dict.ContainsKey(key) && dict[key] != null)
            {
                try { return Convert.ToInt32(dict[key]); }
                catch { }
            }
            return defaultValue;
        }

        private void StopServer()
        {
            try
            {
                if (cts != null) cts.Cancel();
                foreach (var kv in clients)
                    kv.Value.Close();
                clients.Clear();
                if (tcpListener != null) tcpListener.Stop();
                Print("Q7Bridge: Server stopped");
            }
            catch { }
        }
    }
}
