"""数据采集层：获取ROS2节点列表、话题、服务、参数等信息"""

import subprocess
import threading
import time
import re


class NodeInfo:
    """单个节点的信息数据类"""

    def __init__(self, name):
        self.name = name
        self.online = True
        self.publishers = []
        self.subscribers = []
        self.services = []
        self.clients = []
        self.parameters = []

    def __repr__(self):
        return f"NodeInfo(name={self.name}, online={self.online})"


class NodeCollector:
    """节点信息采集器，在后台线程中定时采集"""

    def __init__(self, refresh_interval=2.0, cli_timeout=3):
        self.refresh_interval = refresh_interval
        self.cli_timeout = cli_timeout
        self._lock = threading.Lock()
        self._nodes = {}
        self._running = False
        self._thread = None

    def _run_cli(self, cmd):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.cli_timeout
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
        except Exception:
            return ""

    def get_node_list(self):
        output = self._run_cli(['ros2', 'node', 'list'])
        if not output:
            return []
        return [n.strip() for n in output.split('\n') if n.strip()]

    def parse_node_info(self, node_name):
        output = self._run_cli(['ros2', 'node', 'info', node_name])
        info = NodeInfo(node_name)
        if not output:
            info.online = False
            return info

        current_section = None
        for line in output.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            if 'Publishers:' in stripped:
                current_section = 'publishers'
            elif 'Subscribers:' in stripped:
                current_section = 'subscribers'
            elif 'Services:' in stripped:
                current_section = 'services'
            elif 'Service Clients:' in stripped:
                current_section = 'clients'
            elif 'Parameters:' in stripped:
                current_section = 'parameters'
            elif current_section and ':' in stripped and current_section != 'parameters':
                parts = stripped.split(':')
                topic = parts[0].strip()
                msg_type = parts[1].strip() if len(parts) > 1 else ''
                getattr(info, current_section).append((topic, msg_type))
            elif current_section == 'parameters':
                info.parameters.append(stripped)

        return info

    def collect_once(self):
        node_names = self.get_node_list()
        nodes = {}
        for name in node_names:
            info = self.parse_node_info(name)
            nodes[name] = info
        with self._lock:
            old_nodes = set(self._nodes.keys())
            new_nodes = set(node_names)
            for name in old_nodes - new_nodes:
                self._nodes[name].online = False
            for name in new_nodes:
                self._nodes[name] = nodes[name]
        return nodes

    def get_nodes(self):
        with self._lock:
            return dict(self._nodes)

    def _loop(self):
        while self._running:
            self.collect_once()
            time.sleep(self.refresh_interval)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)