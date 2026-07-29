// Q7AccountManagerAddOn.cs
// NinjaTrader 8 AddOn - Puente NT8 ↔ Q7
// SOLO expone datos de cuentas y ejecuta ordenes. Cero logica de ciclos.

#region Using declarations
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.AddOns;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    public class Q7AccountManagerAddOn : AddOnBase
    {
        private string commandsPath, statusPath;
        private JavaScriptSerializer json = new JavaScriptSerializer();
        private System.Threading.Timer pollTimer;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults) { Name = "Q7AccountManager"; }
            else if (State == State.Configure)
            {
                string bp = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "NinjaTrader 8", "Q7");
                commandsPath = Path.Combine(bp, "commands");
                statusPath = Path.Combine(bp, "status");
                foreach (var d in new[] { commandsPath, statusPath })
                    if (!Directory.Exists(d)) Directory.CreateDirectory(d);
            }
            else if (State == State.Active)
            {
                Print("Q7 Bridge: " + GetAllAccountNames());
                WriteStatus("Bridge ready");
                pollTimer = new System.Threading.Timer(_ => OnPoll(), null, 1000, 1000);
            }
            else if (State == State.Terminated)
            {
                if (pollTimer != null) pollTimer.Dispose();
            }
        }

        private void OnPoll()
        {
            try { ProcessCommands(); } catch { }
            WriteStatus("OK");
        }

        // ============= COMMANDS =============

        private void ProcessCommands()
        {
            if (!Directory.Exists(commandsPath)) return;
            foreach (string file in Directory.GetFiles(commandsPath, "*.json"))
            {
                try
                {
                    string content = File.ReadAllText(file);
                    File.Delete(file);
                    var cmd = json.Deserialize<Dictionary<string, object>>(content);
                    if (cmd == null) continue;

                    string command = GetStr(cmd, "command", "").ToUpper();
                    string targetAccount = GetStr(cmd, "account", "");

                    switch (command)
                    {
                        case "TRADE":
                            ExecuteTrade(cmd);
                            break;
                        case "CLOSE_ALL":
                            CloseAllOnAccount(targetAccount);
                            break;
                    }
                }
                catch { }
            }
        }

        private void ExecuteTrade(Dictionary<string, object> cmd)
        {
            string accountName = GetStr(cmd, "account", "");
            Account acct = FindAccount(accountName);
            if (acct == null) return;

            string instrument = GetStr(cmd, "instrument", "MNQ 09-26");
            int contracts = GetInt(cmd, "contracts", 1);
            string action = GetStr(cmd, "action", "").ToUpper();

            Instrument inst = Instrument.GetInstrument(instrument);
            if (inst == null) return;

            OrderAction oa = action.Contains("LONG") ? OrderAction.Buy : OrderAction.SellShort;
            Order order = acct.CreateOrder(inst, oa, OrderType.Market, TimeInForce.Day,
                contracts, 0, 0, "", "", null);
            acct.Submit(new[] { order });
            Print("Q7: TRADE " + action + " " + contracts + "x " + instrument + " on [" + accountName + "]");
        }

        private void CloseAllOnAccount(string accountName)
        {
            Account acct = FindAccount(accountName);
            if (acct == null) return;
            var orders = new List<Order>();
            foreach (var pos in acct.Positions)
            {
                OrderAction oa = pos.MarketPosition == MarketPosition.Long
                    ? OrderAction.Sell : OrderAction.BuyToCover;
                orders.Add(acct.CreateOrder(pos.Instrument, oa, OrderType.Market,
                    TimeInForce.Day, pos.Quantity, 0, 0, "", "", null));
            }
            if (orders.Count > 0) acct.Submit(orders);
            Print("Q7: CLOSE_ALL on [" + accountName + "]");
        }

        // ============= STATUS =============

        private void WriteStatus(string message)
        {
            var accountList = new List<Dictionary<string, object>>();
            lock (Account.All)
            {
                foreach (Account a in Account.All)
                {
                    try
                    {
                        var posList = new List<Dictionary<string, object>>();
                        foreach (var pos in a.Positions)
                        {
                            posList.Add(new Dictionary<string, object>
                            {
                                ["instrument"] = pos.Instrument != null ? pos.Instrument.FullName : "",
                                ["direction"] = pos.MarketPosition == MarketPosition.Long ? "LONG" : "SHORT",
                                ["quantity"] = pos.Quantity,
                                ["avg_price"] = pos.AveragePrice,
                            });
                        }

                        accountList.Add(new Dictionary<string, object>
                        {
                            ["name"] = a.Name,
                            ["balance"] = a.Get(AccountItem.CashValue, Currency.UsDollar),
                            ["realized_pnl"] = a.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar),
                            ["unrealized_pnl"] = a.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar),
                            ["positions"] = posList
                        });
                    }
                    catch { }
                }
            }

            var status = new Dictionary<string, object>
            {
                ["timestamp"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                ["message"] = message,
                ["accounts"] = accountList
            };

            File.WriteAllText(Path.Combine(statusPath, "status_" + DateTime.Now.ToString("yyyyMMdd") + ".json"),
                              json.Serialize(status));
        }

        // ============= HELPERS =============

        private Account FindAccount(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            lock (Account.All)
            {
                foreach (Account a in Account.All)
                    if (string.Equals(a.Name, name, StringComparison.OrdinalIgnoreCase)) return a;
            }
            return null;
        }

        private string GetAllAccountNames()
        {
            var names = new List<string>();
            lock (Account.All) { foreach (Account a in Account.All) names.Add(a.Name); }
            return string.Join(", ", names);
        }

        private string GetStr(Dictionary<string, object> d, string key, string def)
        {
            if (d.ContainsKey(key) && d[key] != null) return d[key].ToString();
            return def;
        }

        private int GetInt(Dictionary<string, object> d, string key, int def)
        {
            if (d.ContainsKey(key) && d[key] != null)
                try { return Convert.ToInt32(d[key]); } catch { }
            return def;
        }
    }
}
