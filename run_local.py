"""Локальный запуск для разработки/теста: python run_local.py"""
from vdsrpg import config
from vdsrpg.api import app

if __name__ == "__main__":
    print(f"VDS RPG локально: http://localhost:{config.PORT}/app/")
    app.run(host="0.0.0.0", port=config.PORT, debug=True)
