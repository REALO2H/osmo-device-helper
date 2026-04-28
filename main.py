import ttkbootstrap as ttk
from app.config.settings import APP_TITLE, THEME_NAME
from app.UI.main_window import MainWindow


def main():
    app = ttk.Window(themename=THEME_NAME)
    app.title(APP_TITLE)
    app.geometry("1200x760")
    app.minsize(1000, 680)

    MainWindow(app)

    app.mainloop()


if __name__ == "__main__":
    main()