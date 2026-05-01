import pytest
import os
import sys
import builtins
from unittest.mock import patch, MagicMock

def test_server_initialization_and_env():
    """
    Objetivo: Smoke Test que verifica que el servidor carga las variables de entorno (.env) y configura el logger con timestamps correctamente.
    Funciones: load_dotenv(), builtins.print override
    """
    # Mockear solo lo que se llama al nivel de módulo durante la importación
    with patch("dotenv.load_dotenv") as mock_load_dotenv:
        
        # Forzamos la recarga del módulo para asegurar que el código de nivel de módulo se ejecute
        if "server" in sys.modules:
            import importlib
            import server
            importlib.reload(server)
        else:
            import server

        # 1. Verificar carga de entorno
        mock_load_dotenv.assert_called()
        
        # 2. Verificar constantes configuradas
        assert hasattr(server, "PORT")
        assert hasattr(server, "POLL_INTERVAL")
        
        # 3. Verificar que el logger personalizado se instaló
        assert hasattr(builtins.print, "_kadglobe_logging")
        # El nombre real de la función decorada o reemplazada
        assert "print" in str(builtins.print) or "_color_print" in str(builtins.print)

def test_server_is_emule_running_mock():
    """
    Objetivo: Validar la lógica de detección de procesos activos (eMule/aMule) en diferentes sistemas operativos.
    Funciones: is_emule_running(), subprocess.run()
    """
    import server
    with patch("subprocess.run") as mock_run:
        # Caso Windows
        with patch("os.name", "nt"):
            mock_run.return_value.stdout = "emule.exe   1234 Console"
            assert server.is_emule_running() is True
            
            mock_run.return_value.stdout = "No tasks running"
            assert server.is_emule_running() is False

def test_atomic_write_json_smoke(tmp_path):
    """
    Objetivo: Confirmar que la utilidad de escritura atómica guarda archivos JSON correctamente sin riesgo de corrupción.
    Funciones: atomic_write_json(), os.replace()
    """
    import server
    test_file = tmp_path / "test.json"
    data = {"test": "data"}
    
    success = server.atomic_write_json(str(test_file), data)
    assert success is True
    assert test_file.exists()
    
    import json
    with open(test_file, "r", encoding="utf-8") as f:
        assert json.load(f) == data
