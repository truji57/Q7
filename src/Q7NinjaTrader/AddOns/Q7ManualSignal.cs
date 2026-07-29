// Q7ManualSignal.cs  
// NinjaTrader 8 AddOn - Botones LONG/SHORT en ventana flotante
// Escribe senales directamente en signals/

#region Using declarations
using System;
using System.Collections.Generic;
using System.IO;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.AddOns;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    public class Q7ManualSignal : AddOnBase, NinjaTrader.Gui.ITabFactory
    {
        private string signalsPath;
        private JavaScriptSerializer json = new JavaScriptSerializer();
        private TabControlManager tabManager;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "Q7ManualSignal";
                IsConfigured = true;
            }
            else if (State == State.Configure)
            {
                signalsPath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "NinjaTrader 8", "Q7", "signals"
                );
                if (!Directory.Exists(signalsPath))
                    Directory.CreateDirectory(signalsPath);
            }
            else if (State == State.Active)
            {
                Print("Q7 Manual: Ready. Open from Control Center -> New -> Q7 Signal");
            }
        }

        public NTWindow CreateNTWindow()
        {
            return CreateWindow();
        }

        private NTWindow CreateWindow()
        {
            var window = new NTWindow
            {
                Title = "Q7 Signal",
                Width = 260,
                Height = 150,
                Topmost = true,
                WindowStyle = WindowStyle.ToolWindow,
                ResizeMode = ResizeMode.NoResize,
                WindowStartupLocation = WindowStartupLocation.CenterScreen
            };

            var panel = new StackPanel { Margin = new Thickness(20), VerticalAlignment = VerticalAlignment.Center };

            panel.Children.Add(new Label
            {
                Content = "Simular Senal de Trading",
                FontSize = 13,
                FontWeight = FontWeights.Bold,
                Foreground = Brushes.LightGray,
                HorizontalAlignment = HorizontalAlignment.Center,
                Margin = new Thickness(0, 0, 0, 10)
            });

            var btnPanel = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Center
            };

            var btnLong = new Button
            {
                Content = "LONG",
                Width = 90,
                Height = 40,
                FontSize = 14,
                FontWeight = FontWeights.Bold,
                Foreground = Brushes.White,
                Background = new SolidColorBrush(Color.FromRgb(0, 150, 70)),
                Margin = new Thickness(0, 0, 10, 0)
            };
            btnLong.Click += (s, e) => SendSignal("ENTER_LONG");
            btnPanel.Children.Add(btnLong);

            var btnShort = new Button
            {
                Content = "SHORT",
                Width = 90,
                Height = 40,
                FontSize = 14,
                FontWeight = FontWeights.Bold,
                Foreground = Brushes.White,
                Background = new SolidColorBrush(Color.FromRgb(200, 40, 40))
            };
            btnShort.Click += (s, e) => SendSignal("ENTER_SHORT");
            btnPanel.Children.Add(btnShort);

            panel.Children.Add(btnPanel);

            window.Content = panel;
            return window;
        }

        private void SendSignal(string action)
        {
            try
            {
                var signal = new Dictionary<string, object>
                {
                    ["type"] = "SIGNAL",
                    ["timestamp"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                    ["action"] = action,
                    ["order"] = new Dictionary<string, object>
                    {
                        ["instrument"] = "YM",
                        ["sl_ticks"] = 75,
                        ["tp_ticks"] = 90,
                    }
                };

                string fileName = "manual_" + DateTime.Now.ToString("yyyyMMdd_HHmmssfff") + ".json";
                File.WriteAllText(Path.Combine(signalsPath, fileName), json.Serialize(signal));
                Print("Q7 Manual: " + action + " signal sent!");
            }
            catch (Exception ex)
            {
                Print("Q7 Manual error: " + ex.Message);
            }
        }

        #region ITabFactory
        NTWindow NinjaTrader.Gui.ITabFactory.CreateNTWindow() { return CreateWindow(); }
        #endregion
    }
}
