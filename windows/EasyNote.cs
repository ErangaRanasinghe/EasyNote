// Easy Note - a tiny scratch pad that hides on the right edge of the screen.
// Publisher: EMR Industries
//
// Move the mouse to the far right edge of the screen and a small tab appears.
// Click it and a borderless, always-on-top note window opens just above the
// taskbar, centred. It stays open (and on top) until you click the tab again.
//
// Built with the C# compiler that ships with Windows (.NET Framework 4.x),
// so it sticks to C# 5 syntax. See build.bat.

using System;
using System.ComponentModel;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using System.Reflection;
using Microsoft.Win32;

[assembly: AssemblyTitle("Easy Note")]
[assembly: AssemblyProduct("Easy Note")]
[assembly: AssemblyDescription("Quick scratch pad on the edge of your screen")]
[assembly: AssemblyCompany("EMR Industries")]
[assembly: AssemblyCopyright("Copyright (c) 2026 EMR Industries")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

static class AppInfo
{
    public const string Name = "Easy Note";
    public const string Version = "1.0.0";
    public const string Publisher = "EMR Industries";

    static Image logo;
    public static Image Logo
    {
        get
        {
            if (logo == null)
            {
                try
                {
                    using (Stream st = typeof(AppInfo).Assembly.GetManifestResourceStream("logo.png"))
                        if (st != null) using (Image img = Image.FromStream(st)) logo = new Bitmap(img);
                }
                catch { }
            }
            return logo;
        }
    }

    public static Icon TrayIcon()
    {
        try
        {
            using (Stream st = typeof(AppInfo).Assembly.GetManifestResourceStream("logo.ico"))
                if (st != null) return new Icon(st, SystemInformation.SmallIconSize);
        }
        catch { }
        return Art.MakeIcon();
    }

    // The build date is the date EasyNote.exe was built
    public static string BuildDate
    {
        get
        {
            try { return File.GetLastWriteTime(Application.ExecutablePath).ToString("d MMM yyyy", System.Globalization.CultureInfo.InvariantCulture); }
            catch { return ""; }
        }
    }
}

static class Program
{
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();

    [STAThread]
    static void Main()
    {
        bool created;
        using (Mutex m = new Mutex(true, "EasyNote_SingleInstance_5c2e91", out created))
        {
            if (!created) return;               // already running
            try { SetProcessDPIAware(); } catch { }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new EasyNoteApp());
        }
    }
}

static class Native
{
    public const int WS_EX_TOPMOST = 0x00000008;
    public const int WS_EX_TOOLWINDOW = 0x00000080;
    public const int WS_EX_NOACTIVATE = 0x08000000;
    public const int WS_EX_LAYERED = 0x00080000;
    [DllImport("user32.dll")] public static extern bool SetLayeredWindowAttributes(IntPtr hWnd, uint key, byte alpha, uint flags);
    public const int WM_NCLBUTTONDOWN = 0xA1;
    public const int HTCAPTION = 2;
    public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
    public const uint SWP_NOSIZE = 0x0001, SWP_NOMOVE = 0x0002, SWP_NOACTIVATE = 0x0010;

    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ReleaseCapture();
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr w, IntPtr l);

    [DllImport("dwmapi.dll")] public static extern int DwmSetWindowAttribute(IntPtr hWnd, int attr, ref int value, int size);
    [DllImport("uxtheme.dll", CharSet = CharSet.Unicode)] public static extern int SetWindowTheme(IntPtr hWnd, string appName, string idList);

    // Windows 11 rounded corners (ignored on Windows 10)
    public static void RoundCorners(Form f, bool small)
    {
        try { int pref = small ? 3 : 2; DwmSetWindowAttribute(f.Handle, 33, ref pref, 4); } catch { }
    }

    public static void ForceTopmost(Form f)
    {
        SetWindowPos(f.Handle, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
    }
}

// Settings and the note text live in %APPDATA%\EasyNote
static class Store
{
    public static readonly string Dir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "EasyNote");

    // Bring over the text and settings saved by the earlier EdgeNote version
    static Store()
    {
        try
        {
            string old = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "EdgeNote");
            if (Directory.Exists(old) && !Directory.Exists(Dir)) Directory.Move(old, Dir);
        }
        catch { }
    }
    static readonly string NotePath = Path.Combine(Dir, "note.txt");
    static readonly string FontPath = Path.Combine(Dir, "font.txt");

    public static string LoadText()
    {
        try { return File.Exists(NotePath) ? File.ReadAllText(NotePath) : ""; } catch { return ""; }
    }
    public static void SaveText(string text)
    {
        try { Directory.CreateDirectory(Dir); File.WriteAllText(NotePath, text); } catch { }
    }
    static readonly string OpacityPath = Path.Combine(Dir, "opacity.txt");

    public static double LoadOpacity()
    {
        try
        {
            double v;
            if (File.Exists(OpacityPath) &&
                double.TryParse(File.ReadAllText(OpacityPath).Trim(), System.Globalization.NumberStyles.Float,
                                System.Globalization.CultureInfo.InvariantCulture, out v) && v >= 0.3 && v <= 1.0)
                return v;
        }
        catch { }
        return 0.85;
    }
    public static void SaveOpacity(double v)
    {
        try { Directory.CreateDirectory(Dir); File.WriteAllText(OpacityPath, v.ToString(System.Globalization.CultureInfo.InvariantCulture)); } catch { }
    }

    public static Font LoadFont()
    {
        try
        {
            if (File.Exists(FontPath))
            {
                Font f = new FontConverter().ConvertFromInvariantString(File.ReadAllText(FontPath).Trim()) as Font;
                if (f != null) return f;
            }
        }
        catch { }
        return new Font("Segoe UI", 11f);
    }
    public static void SaveFont(Font f)
    {
        try { Directory.CreateDirectory(Dir); File.WriteAllText(FontPath, new FontConverter().ConvertToInvariantString(f)); } catch { }
    }
}

// ---------------------------------------------------------------------------
// Follows the Windows theme: light/dark app mode and the accent color
// ---------------------------------------------------------------------------
class Theme
{
    public bool Dark;
    public Color Accent, AccentHover, Back, Bar, Text, Muted, Line, Hover, Pressed;

    public static Theme Current()
    {
        Theme t = new Theme();
        t.Dark = ReadDword(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", 1) == 0;

        // DWM stores the accent as 0xAABBGGRR
        int abgr = ReadDword(@"Software\Microsoft\Windows\DWM", "AccentColor", -1);
        t.Accent = abgr == -1 ? Color.FromArgb(0, 120, 215)
                              : Color.FromArgb(abgr & 0xFF, (abgr >> 8) & 0xFF, (abgr >> 16) & 0xFF);
        t.AccentHover = Blend(t.Accent, t.Dark ? Color.White : Color.Black, 0.18f);

        if (t.Dark)
        {
            t.Back = Color.FromArgb(32, 32, 32);
            t.Bar = Color.FromArgb(43, 43, 43);
            t.Text = Color.FromArgb(240, 240, 240);
            t.Muted = Color.FromArgb(160, 160, 160);
            t.Line = Color.FromArgb(70, 70, 70);
            t.Hover = Color.FromArgb(61, 61, 61);
            t.Pressed = Color.FromArgb(75, 75, 75);
        }
        else
        {
            t.Back = Color.FromArgb(255, 255, 255);
            t.Bar = Color.FromArgb(243, 243, 243);
            t.Text = Color.FromArgb(28, 28, 28);
            t.Muted = Color.FromArgb(96, 96, 96);
            t.Line = Color.FromArgb(200, 200, 200);
            t.Hover = Color.FromArgb(228, 228, 228);
            t.Pressed = Color.FromArgb(214, 214, 214);
        }
        return t;
    }

    static int ReadDword(string key, string name, int fallback)
    {
        try
        {
            using (RegistryKey k = Registry.CurrentUser.OpenSubKey(key))
            {
                object v = k == null ? null : k.GetValue(name);
                return v is int ? (int)v : fallback;
            }
        }
        catch { return fallback; }
    }

    static Color Blend(Color a, Color b, float amount)
    {
        return Color.FromArgb(
            (int)(a.R + (b.R - a.R) * amount),
            (int)(a.G + (b.G - a.G) * amount),
            (int)(a.B + (b.B - a.B) * amount));
    }
}

// ---------------------------------------------------------------------------
// The app: watches the mouse, owns the edge tab, the note window and tray icon
// ---------------------------------------------------------------------------
class EasyNoteApp : ApplicationContext
{
    const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
    const string RunName = "EasyNote";
    const string OldRunName = "EdgeNote";

    readonly EdgeTab tab;
    readonly NoteWindow note;
    readonly NotifyIcon tray;
    readonly System.Windows.Forms.Timer poll;
    readonly ToolStripMenuItem startupItem;
    DateTime lastNearEdge = DateTime.MinValue;

    public EasyNoteApp()
    {
        note = new NoteWindow();
        tab = new EdgeTab();
        tab.TabClicked += delegate { ToggleNote(); };

        ContextMenuStrip menu = new ContextMenuStrip();
        menu.Items.Add("Open note", null, delegate { ShowNote(); });
        menu.Items.Add("Change font...", null, delegate { note.ChooseFont(); });

        ToolStripMenuItem trans = new ToolStripMenuItem("Transparency");
        int[] levels = { 100, 95, 90, 85, 80, 70, 60 };
        foreach (int lvl in levels)
        {
            int level = lvl;
            ToolStripMenuItem it = new ToolStripMenuItem(level == 100 ? "None (solid)" : (100 - level) + "% see-through");
            it.Tag = level;
            it.Click += delegate
            {
                note.SetTransparency(level / 100.0);
                foreach (ToolStripMenuItem x in trans.DropDownItems) x.Checked = (int)x.Tag == level;
            };
            it.Checked = Math.Abs(Store.LoadOpacity() * 100 - level) < 0.5;
            trans.DropDownItems.Add(it);
        }
        menu.Items.Add(trans);
        MigrateStartup();
        startupItem = new ToolStripMenuItem("Start with Windows", null, delegate { ToggleStartup(); });
        startupItem.Checked = IsStartupOn();
        menu.Items.Add(startupItem);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("About " + AppInfo.Name, null, delegate { new SplashWindow(Theme.Current()).ShowFor(2000); });
        menu.Items.Add("Exit", null, delegate { ExitApp(); });

        tray = new NotifyIcon();
        tray.Icon = AppInfo.TrayIcon();
        tray.Text = AppInfo.Name + " - move the mouse to the right edge";
        tray.ContextMenuStrip = menu;
        tab.ContextMenuStrip = menu;      // right-click the edge tab
        note.AttachMenu(menu);            // menu button / right-click on the note's top strip
        tray.MouseClick += delegate(object s, MouseEventArgs e) { if (e.Button == MouseButtons.Left) ToggleNote(); };
        tray.Visible = true;

        poll = new System.Windows.Forms.Timer();
        poll.Interval = 80;
        poll.Tick += Poll;
        poll.Start();

        // Re-theme live when Windows switches light/dark or the accent color
        IntPtr ensureHandle = note.Handle;
        SystemEvents.UserPreferenceChanged += OnPreferenceChanged;
        ApplyTheme();

        // Start-up window: logo, version, publisher - closes itself after 2 seconds
        new SplashWindow(Theme.Current()).ShowFor(2000);
    }

    // If "Start with Windows" was on in the old EdgeNote, point it at Easy Note instead
    void MigrateStartup()
    {
        try
        {
            using (RegistryKey k = Registry.CurrentUser.OpenSubKey(RunKey, true))
            {
                if (k != null && k.GetValue(OldRunName) != null)
                {
                    k.DeleteValue(OldRunName, false);
                    k.SetValue(RunName, "\"" + Application.ExecutablePath + "\"");
                }
            }
        }
        catch { }
    }

    void OnPreferenceChanged(object sender, UserPreferenceChangedEventArgs e)
    {
        try { note.BeginInvoke((MethodInvoker)ApplyTheme); } catch { }
    }

    void ApplyTheme()
    {
        Theme t = Theme.Current();
        note.ApplyTheme(t);
        tab.ApplyTheme(t);
    }

    void Poll(object sender, EventArgs e)
    {
        // Keep the note above everything, even when you click other windows
        if (note.Visible) Native.ForceTopmost(note);

        Point p = Cursor.Position;
        Screen sc = Screen.FromPoint(p);
        bool atEdge = p.X >= sc.Bounds.Right - 2;
        bool overTab = tab.Visible && tab.Bounds.Contains(p);

        if (atEdge || overTab)
        {
            lastNearEdge = DateTime.Now;
            if (!tab.Visible) tab.ShowAt(sc, p.Y);
            else Native.ForceTopmost(tab);
        }
        else if (tab.Visible && (DateTime.Now - lastNearEdge).TotalMilliseconds > 1200)
        {
            tab.Hide();
        }
    }

    void ToggleNote()
    {
        if (note.Visible) note.HideNote();
        else ShowNote();
    }

    void ShowNote()
    {
        Screen sc = tab.Visible ? Screen.FromControl(tab) : Screen.FromPoint(Cursor.Position);
        note.ShowNote(sc);
    }

    bool IsStartupOn()
    {
        try
        {
            using (RegistryKey k = Registry.CurrentUser.OpenSubKey(RunKey))
                return k != null && k.GetValue(RunName) != null;
        }
        catch { return false; }
    }

    void ToggleStartup()
    {
        try
        {
            using (RegistryKey k = Registry.CurrentUser.CreateSubKey(RunKey))
            {
                if (IsStartupOn()) k.DeleteValue(RunName, false);
                else k.SetValue(RunName, "\"" + Application.ExecutablePath + "\"");
            }
        }
        catch (Exception ex) { MessageBox.Show("Could not change the startup setting:\n" + ex.Message, AppInfo.Name); }
        startupItem.Checked = IsStartupOn();
    }

    void ExitApp()
    {
        note.SaveNow();
        SystemEvents.UserPreferenceChanged -= OnPreferenceChanged;
        poll.Stop();
        tray.Visible = false;
        tray.Dispose();
        ExitThread();
    }
}

// ---------------------------------------------------------------------------
// The little tab on the right edge
// ---------------------------------------------------------------------------
class EdgeTab : Form
{
    public event EventHandler TabClicked;
    bool hover;
    // Always Windows blue, whatever the accent color is
    readonly Color accent = Color.FromArgb(0, 120, 215), accentHover = Color.FromArgb(0, 98, 176);

    public void ApplyTheme(Theme t) { Invalidate(); }

    public EdgeTab()
    {
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.Manual;
        TopMost = true;
        DoubleBuffered = true;
        BackColor = Color.FromArgb(44, 120, 214);
        Cursor = Cursors.Hand;

        float s = Art.Scale(this);
        Size = new Size((int)(28 * s), (int)(84 * s));
        Region = Art.LeftRoundedRegion(Width, Height, (int)(10 * s));

        MouseEnter += delegate { hover = true; Invalidate(); };
        MouseLeave += delegate { hover = false; Invalidate(); };
        MouseUp += delegate(object o, MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left && TabClicked != null) TabClicked(this, EventArgs.Empty);
        };
    }

    // Never steal focus from the app you are working in
    protected override bool ShowWithoutActivation { get { return true; } }

    protected override CreateParams CreateParams
    {
        get
        {
            CreateParams cp = base.CreateParams;
            cp.ExStyle |= Native.WS_EX_TOOLWINDOW | Native.WS_EX_NOACTIVATE | Native.WS_EX_TOPMOST;
            return cp;
        }
    }

    public void ShowAt(Screen sc, int cursorY)
    {
        Rectangle wa = sc.WorkingArea;
        int y = cursorY - Height / 2;
        y = Math.Max(wa.Top + 4, Math.Min(y, wa.Bottom - Height - 4));
        Location = new Point(sc.Bounds.Right - Width, y);
        Show();
        Native.ForceTopmost(this);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        e.Graphics.Clear(hover ? accentHover : accent);
        Art.DrawPencil(e.Graphics, new RectangleF(Width * 0.18f, Height * 0.5f - Width * 0.32f, Width * 0.64f, Width * 0.64f), Color.White);
    }
}

// ---------------------------------------------------------------------------
// The note window: no title bar, ~2 inches tall, sits above the taskbar
// ---------------------------------------------------------------------------
class NoteWindow : Form
{
    readonly TextBox box;
    readonly Panel bar;
    readonly System.Windows.Forms.Timer saveTimer;
    readonly Label status;
    readonly Panel inner;
    readonly System.Collections.Generic.List<Button> buttons = new System.Collections.Generic.List<Button>();

    public void ApplyTheme(Theme t)
    {
        BackColor = t.Line;                 // 1px border
        bar.BackColor = t.Bar;
        status.ForeColor = t.Muted;
        inner.BackColor = t.Back;
        box.BackColor = t.Back;
        box.ForeColor = t.Text;
        foreach (Button b in buttons)
        {
            b.BackColor = t.Bar;
            b.ForeColor = t.Text;
            b.FlatAppearance.MouseOverBackColor = t.Hover;
            b.FlatAppearance.MouseDownBackColor = t.Pressed;
        }
        // dark or light scrollbar to match
        try { Native.SetWindowTheme(box.Handle, t.Dark ? "DarkMode_Explorer" : "Explorer", null); } catch { }
        Invalidate(true);
    }

    double transparency = 0.85;

    // Window-level transparency, applied straight to the window so it always takes effect
    public void SetTransparency(double level)
    {
        transparency = Math.Max(0.3, Math.Min(1.0, level));
        Store.SaveOpacity(transparency);
        ApplyAlpha();
    }

    void ApplyAlpha()
    {
        if (!IsHandleCreated) return;
        Native.SetLayeredWindowAttributes(Handle, 0, (byte)Math.Round(transparency * 255), 0x2 /* LWA_ALPHA */);
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        ApplyAlpha();
        Native.RoundCorners(this, false);
    }

    // Right-click the top strip, or click the menu button, for font, transparency and Exit
    public void AttachMenu(ContextMenuStrip menu)
    {
        bar.ContextMenuStrip = menu;
        status.ContextMenuStrip = menu;
        Button m = MakeButton("⋯", "Menu: font, transparency, start with Windows, Exit", null, Art.Scale(this));
        m.Click += delegate { menu.Show(m, new Point(0, m.Height)); };
        bar.Controls.Add(m);
        ApplyTheme(Theme.Current());
    }

    public NoteWindow()
    {
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.Manual;
        TopMost = true;
        KeyPreview = true;
        transparency = Store.LoadOpacity();             // default 85% solid (see-through)
        BackColor = Color.FromArgb(150, 160, 170);     // shows as a 1px border
        Padding = new Padding(1);

        float s = Art.Scale(this);
        float dpi = Art.Dpi(this);
        Size = new Size((int)(4.2f * dpi), (int)(2.0f * dpi));   // about 4.2 x 2 inches

        // --- top strip: drag handle + buttons ---
        bar = new Panel();
        bar.Dock = DockStyle.Top;
        bar.Height = (int)(26 * s);
        bar.BackColor = Color.FromArgb(238, 241, 245);
        bar.Cursor = Cursors.SizeAll;
        bar.MouseDown += DragWindow;

        status = new Label();
        status.Text = AppInfo.Name;
        status.AutoSize = false;
        status.Dock = DockStyle.Fill;
        status.TextAlign = ContentAlignment.MiddleLeft;
        status.Padding = new Padding((int)(6 * s), 0, 0, 0);
        status.ForeColor = Color.FromArgb(90, 100, 110);
        status.Font = new Font("Segoe UI", 8.5f);
        status.MouseDown += DragWindow;

        bar.Controls.Add(status);
        bar.Controls.Add(MakeButton("Clear", "Clear all text", delegate { ClearText(); }, s));
        bar.Controls.Add(MakeButton("Copy", "Copy selection, or everything if nothing is selected", delegate { CopyText(); }, s));
        bar.Controls.Add(MakeButton("Aa", "Change font", delegate { ChooseFont(); }, s));

        // --- typing area ---
        box = new TextBox();
        box.Multiline = true;
        box.AcceptsReturn = true;
        box.AcceptsTab = true;
        box.WordWrap = true;
        box.ScrollBars = ScrollBars.Vertical;
        box.BorderStyle = BorderStyle.None;
        box.Dock = DockStyle.Fill;
        box.BackColor = Color.White;
        box.Font = Store.LoadFont();
        box.Text = Store.LoadText();
        box.KeyDown += BoxKeyDown;
        box.TextChanged += delegate { saveTimer.Stop(); saveTimer.Start(); };

        inner = new Panel();
        inner.Dock = DockStyle.Fill;
        inner.BackColor = Color.White;
        inner.Padding = new Padding((int)(8 * s), (int)(6 * s), (int)(4 * s), (int)(4 * s));
        inner.Controls.Add(box);

        Controls.Add(inner);
        Controls.Add(bar);

        saveTimer = new System.Windows.Forms.Timer();
        saveTimer.Interval = 700;
        saveTimer.Tick += delegate { saveTimer.Stop(); SaveNow(); };
    }

    protected override CreateParams CreateParams
    {
        get
        {
            CreateParams cp = base.CreateParams;
            cp.ExStyle |= Native.WS_EX_TOOLWINDOW | Native.WS_EX_TOPMOST | Native.WS_EX_LAYERED;
            return cp;
        }
    }

    Button MakeButton(string text, string tip, EventHandler onClick, float s)
    {
        Button b = new Button();
        b.Text = text;
        b.Dock = DockStyle.Right;
        b.Width = (int)((text.Length > 2 ? 46 : 30) * s);
        b.FlatStyle = FlatStyle.Flat;
        b.FlatAppearance.BorderSize = 0;
        b.FlatAppearance.MouseOverBackColor = Color.FromArgb(214, 222, 232);
        b.Font = new Font("Segoe UI", 8.5f);
        b.ForeColor = Color.FromArgb(40, 50, 60);
        b.Cursor = Cursors.Hand;
        b.TabStop = false;
        if (onClick != null) b.Click += onClick;
        new ToolTip().SetToolTip(b, tip);
        buttons.Add(b);
        return b;
    }

    void DragWindow(object sender, MouseEventArgs e)
    {
        if (e.Button != MouseButtons.Left) return;
        Native.ReleaseCapture();
        Native.SendMessage(Handle, Native.WM_NCLBUTTONDOWN, (IntPtr)Native.HTCAPTION, IntPtr.Zero);
    }

    void BoxKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Control && e.KeyCode == Keys.A) { box.SelectAll(); e.SuppressKeyPress = true; }
    }

    protected override bool ProcessCmdKey(ref Message msg, Keys keyData)
    {
        if (keyData == (Keys.Control | Keys.Shift | Keys.C)) { CopyText(); return true; }
        return base.ProcessCmdKey(ref msg, keyData);
    }

    public void ShowNote(Screen sc)
    {
        Rectangle wa = sc.WorkingArea;            // working area excludes the taskbar
        int gap = (int)(8 * Art.Scale(this));
        Location = new Point(wa.Left + (wa.Width - Width) / 2, wa.Bottom - Height - gap);   // bottom centre
        Show();
        Native.ForceTopmost(this);
        Activate();
        Native.SetForegroundWindow(Handle);
        box.Focus();
        box.SelectionStart = box.TextLength;
        box.ScrollToCaret();
    }

    public void HideNote()
    {
        SaveNow();
        Hide();
    }

    void CopyText()
    {
        string t = box.SelectionLength > 0 ? box.SelectedText : box.Text;
        if (t.Length == 0) { Flash("Nothing to copy"); return; }
        try { Clipboard.SetText(t); Flash(box.SelectionLength > 0 ? "Selection copied" : "All text copied"); }
        catch { Flash("Clipboard busy, try again"); }
        box.Focus();
    }

    void ClearText()
    {
        if (box.TextLength == 0) return;
        box.SelectAll();
        box.Paste("");          // keeps Ctrl+Z working
        Flash("Cleared (Ctrl+Z to undo)");
        box.Focus();
    }

    public void ChooseFont()
    {
        using (FontDialog d = new FontDialog())
        {
            d.Font = box.Font;
            d.ShowEffects = false;
            if (d.ShowDialog(this) == DialogResult.OK)
            {
                box.Font = d.Font;
                Store.SaveFont(d.Font);
            }
        }
        if (Visible) { Native.ForceTopmost(this); box.Focus(); }
    }

    public void SaveNow() { Store.SaveText(box.Text); }

    void Flash(string message)
    {
        status.Text = message;
        System.Windows.Forms.Timer t = new System.Windows.Forms.Timer();
        t.Interval = 1600;
        t.Tick += delegate { status.Text = AppInfo.Name; t.Stop(); t.Dispose(); };
        t.Start();
    }
}

// ---------------------------------------------------------------------------
// Start-up window: logo, name, version, build date and publisher
// ---------------------------------------------------------------------------
class SplashWindow : Form
{
    readonly Theme theme;
    readonly float s;

    public SplashWindow(Theme t)
    {
        theme = t;
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.Manual;
        TopMost = true;
        DoubleBuffered = true;
        BackColor = t.Back;
        s = Art.Scale(this);
        Size = new Size((int)(360 * s), (int)(132 * s));
        Click += delegate { Close(); };
    }

    protected override bool ShowWithoutActivation { get { return true; } }

    protected override CreateParams CreateParams
    {
        get
        {
            CreateParams cp = base.CreateParams;
            cp.ExStyle |= Native.WS_EX_TOOLWINDOW | Native.WS_EX_TOPMOST | Native.WS_EX_NOACTIVATE;
            return cp;
        }
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        Native.RoundCorners(this, false);
    }

    public void ShowFor(int milliseconds)
    {
        Rectangle wa = Screen.PrimaryScreen.WorkingArea;
        Location = new Point(wa.Left + (wa.Width - Width) / 2, wa.Top + (wa.Height - Height) / 2);
        Show();
        Native.ForceTopmost(this);
        System.Windows.Forms.Timer t = new System.Windows.Forms.Timer();
        t.Interval = milliseconds;
        t.Tick += delegate { t.Stop(); t.Dispose(); Close(); };
        t.Start();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.InterpolationMode = InterpolationMode.HighQualityBicubic;

        int pad = (int)(22 * s), logo = (int)(88 * s);
        Rectangle logoRect = new Rectangle(pad, (Height - logo) / 2, logo, logo);
        if (AppInfo.Logo != null) g.DrawImage(AppInfo.Logo, logoRect);
        else using (Icon ic = Art.MakeIcon()) g.DrawIcon(ic, logoRect);

        int x = logoRect.Right + (int)(18 * s);
        int y = (int)(26 * s);
        using (Font title = new Font("Segoe UI Semibold", 16f))
        using (Font small = new Font("Segoe UI", 9f))
        {
            TextRenderer.DrawText(g, AppInfo.Name, title, new Point(x, y), theme.Text);
            y += (int)(36 * s);
            TextRenderer.DrawText(g, "Version " + AppInfo.Version + "   \u00B7   Build " + AppInfo.BuildDate, small, new Point(x, y), theme.Muted);
            y += (int)(20 * s);
            TextRenderer.DrawText(g, "Publisher: " + AppInfo.Publisher, small, new Point(x, y), theme.Muted);
        }

        // blue strip along the bottom, and a thin border for Windows 10
        using (SolidBrush b = new SolidBrush(Color.FromArgb(0, 120, 215)))
            g.FillRectangle(b, 0, Height - (int)(4 * s), Width, (int)(4 * s));
        using (Pen p = new Pen(theme.Line))
            g.DrawRectangle(p, 0, 0, Width - 1, Height - 1);
    }
}

// ---------------------------------------------------------------------------
// Drawing helpers
// ---------------------------------------------------------------------------
static class Art
{
    public static float Dpi(Control c)
    {
        using (Graphics g = c.CreateGraphics()) return g.DpiY;
    }
    public static float Scale(Control c) { return Dpi(c) / 96f; }

    public static Region LeftRoundedRegion(int w, int h, int r)
    {
        GraphicsPath p = new GraphicsPath();
        p.AddArc(0, 0, r * 2, r * 2, 180, 90);
        p.AddLine(r, 0, w, 0);
        p.AddLine(w, 0, w, h);
        p.AddLine(w, h, r, h);
        p.AddArc(0, h - r * 2, r * 2, r * 2, 90, 90);
        p.CloseFigure();
        return new Region(p);
    }

    // A simple pencil, drawn so no icon file is needed
    public static void DrawPencil(Graphics g, RectangleF r, Color c)
    {
        GraphicsState st = g.Save();
        g.TranslateTransform(r.X + r.Width / 2, r.Y + r.Height / 2);
        g.RotateTransform(-45);
        float L = r.Width * 1.25f, W = r.Width * 0.28f;
        using (SolidBrush b = new SolidBrush(c))
        {
            g.FillRectangle(b, -L / 2 + W, -W / 2, L - W * 1.6f, W);                 // body
            g.FillPolygon(b, new PointF[] {                                             // tip
                new PointF(-L / 2 + W * 0.85f, -W / 2), new PointF(-L / 2, 0), new PointF(-L / 2 + W * 0.85f, W / 2) });
            g.FillRectangle(b, L / 2 - W * 0.45f, -W / 2, W * 0.45f, W);              // eraser
        }
        g.Restore(st);
    }

    public static Icon MakeIcon()
    {
        Bitmap bmp = new Bitmap(32, 32);
        using (Graphics g = Graphics.FromImage(bmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (SolidBrush bg = new SolidBrush(Color.FromArgb(44, 120, 214)))
                g.FillEllipse(bg, 1, 1, 30, 30);
            DrawPencil(g, new RectangleF(7, 7, 18, 18), Color.White);
        }
        return Icon.FromHandle(bmp.GetHicon());
    }
}
