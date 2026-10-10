"""GUI可视化面板：节点列表 + 详情 + 状态栏"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
from ros2_node_monitor.collector import NodeCollector


STATUS_COLORS = {
    'online': '#4CAF50',
    'offline': '#9E9E9E',
    'active': '#2196F3',
    'inactive': '#FF9800',
    'error': '#F44336',
}


class NodeMonitorGUI:
    """节点监控主界面"""

    def __init__(self, refresh_interval_ms=2000, cli_timeout=3):
        self.refresh_interval_ms = refresh_interval_ms
        self.collector = NodeCollector(
            refresh_interval=refresh_interval_ms / 1000.0,
            cli_timeout=cli_timeout
        )
        self._build_ui()

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("ROS2 节点监控面板")
        self.root.geometry("960x640")
        self.root.minsize(800, 480)

        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=5, pady=5)

        self.refresh_btn = tk.Button(
            top_frame, text="刷新", command=self._manual_refresh
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=2)

        self.exit_btn = tk.Button(
            top_frame, text="退出", command=self._on_exit
        )
        self.exit_btn.pack(side=tk.LEFT, padx=2)

        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = tk.Frame(main_frame, width=280)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.pack_propagate(False)

        tk.Label(left_frame, text="节点列表", font=('Arial', 11, 'bold')).pack(
            anchor=tk.W
        )

        tree_frame = tk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.node_tree = ttk.Treeview(
            tree_frame,
            columns=('status',),
            show='tree headings',
            height=20
        )
        self.node_tree.heading('#0', text='节点名称')
        self.node_tree.heading('status', text='状态')
        self.node_tree.column('#0', width=200)
        self.node_tree.column('status', width=60, anchor=tk.CENTER)

        tree_scroll = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.node_tree.yview
        )
        self.node_tree.configure(yscrollcommand=tree_scroll.set)
        self.node_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.node_tree.bind('<<TreeviewSelect>>', self._on_node_selected)

        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(right_frame, text="节点详情", font=('Arial', 11, 'bold')).pack(
            anchor=tk.W
        )

        self.detail_text = tk.Text(
            right_frame, wrap=tk.WORD, font=('Courier', 10), state=tk.DISABLED
        )
        detail_scroll = ttk.Scrollbar(
            right_frame, orient=tk.VERTICAL, command=self.detail_text.yview
        )
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_bar = tk.Label(
            self.root, text="就绪", anchor=tk.W, relief=tk.SUNKEN
        )
        self.status_bar.pack(fill=tk.X, padx=5, pady=(0, 5))

    def _update_status_bar(self, node_count):
        now = datetime.now().strftime("%H:%M:%S")
        self.status_bar.config(
            text=f"节点数: {node_count} | 上次刷新: {now}"
        )

    def _refresh_tree(self):
        nodes = self.collector.get_nodes()
        existing_items = set(self.node_tree.get_children())
        current_names = set(nodes.keys())

        for item_id in existing_items - current_names:
            self.node_tree.delete(item_id)

        for name, info in nodes.items():
            status_text = "在线" if info.online else "离线"
            existing = self.node_tree.get_children()
            found = False
            for item_id in existing:
                if self.node_tree.item(item_id)['text'] == name:
                    self.node_tree.item(item_id, values=(status_text,))
                    found = True
                    break
            if not found:
                self.node_tree.insert('', tk.END, text=name, values=(status_text,))

        self._update_status_bar(len([n for n in nodes.values() if n.online]))

    def _on_node_selected(self, event):
        selected = self.node_tree.selection()
        if not selected:
            return
        node_name = self.node_tree.item(selected[0])['text']
        nodes = self.collector.get_nodes()
        info = nodes.get(node_name)
        if not info:
            return

        lines = [f"节点: {info.name}", f"状态: {'在线' if info.online else '离线'}", ""]

        if info.publishers:
            lines.append("发布者:")
            for topic, msg_type in info.publishers:
                lines.append(f"  {topic}  [{msg_type}]")
            lines.append("")

        if info.subscribers:
            lines.append("订阅者:")
            for topic, msg_type in info.subscribers:
                lines.append(f"  {topic}  [{msg_type}]")
            lines.append("")

        if info.services:
            lines.append("服务:")
            for srv, srv_type in info.services:
                lines.append(f"  {srv}  [{srv_type}]")
            lines.append("")

        if info.clients:
            lines.append("服务客户端:")
            for srv, srv_type in info.clients:
                lines.append(f"  {srv}  [{srv_type}]")
            lines.append("")

        if info.parameters:
            lines.append("参数:")
            for param in info.parameters:
                lines.append(f"  {param}")
            lines.append("")

        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete('1.0', tk.END)
        self.detail_text.insert(tk.END, '\n'.join(lines))
        self.detail_text.config(state=tk.DISABLED)

    def _auto_refresh(self):
        self._refresh_tree()
        self.root.after(self.refresh_interval_ms, self._auto_refresh)

    def _manual_refresh(self):
        self.collector.collect_once()
        self._refresh_tree()

    def _on_exit(self):
        self.collector.stop()
        self.root.destroy()

    def run(self):
        self.collector.start()
        self._auto_refresh()
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)
        self.root.mainloop()


def main():
    gui = NodeMonitorGUI()
    gui.run()


if __name__ == '__main__':
    main()