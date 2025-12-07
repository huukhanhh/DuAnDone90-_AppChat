# client/views/create_group_dialog.py
from PySide6 import QtWidgets, QtCore, QtGui


class CreateGroupDialog(QtWidgets.QDialog):
    def __init__(self, parent, user_list):
        super().__init__(parent)
        self.user_list = user_list  # Danh sách tất cả user lấy từ server
        self.selected_members = []

        self.setWindowTitle("Tạo nhóm mới")
        self.setFixedSize(400, 500)
        self.setStyleSheet("background-color: white;")

        layout = QtWidgets.QVBoxLayout(self)

        # 1. Tên nhóm
        layout.addWidget(QtWidgets.QLabel("Đặt tên nhóm:"))
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Ví dụ: Nhóm Ăn Trưa...")
        self.name_input.setStyleSheet("""
            QLineEdit { border: 1px solid #ddd; border-radius: 5px; padding: 8px; }
        """)
        layout.addWidget(self.name_input)

        # 2. Tìm kiếm thành viên
        layout.addWidget(QtWidgets.QLabel("Thêm thành viên:"))
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Tìm tên người dùng...")
        self.search_input.setStyleSheet("""
            QLineEdit { border: 1px solid #ddd; border-radius: 15px; padding: 5px 10px; background-color: #f8f9fa; }
        """)
        self.search_input.textChanged.connect(self.filter_users)
        layout.addWidget(self.search_input)

        # 3. Danh sách User (Dạng Checkbox)
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setStyleSheet("border: none;")
        layout.addWidget(self.list_widget)

        # 4. Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_cancel = QtWidgets.QPushButton("Hủy")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_create = QtWidgets.QPushButton("Tạo nhóm")
        self.btn_create.setStyleSheet("background-color: #667eea; color: white; font-weight: bold; padding: 8px;")
        self.btn_create.clicked.connect(self.handle_create)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_create)
        layout.addLayout(btn_layout)

        # Load users ban đầu
        self.populate_list(self.user_list)

    def populate_list(self, users):
        self.list_widget.clear()
        for user in users:
            # Tạo Item
            item = QtWidgets.QListWidgetItem()

            # Tạo Widget con (Avatar + Tên + Checkbox)
            widget = QtWidgets.QWidget()
            h_layout = QtWidgets.QHBoxLayout(widget)
            h_layout.setContentsMargins(5, 5, 5, 5)

            # Checkbox
            checkbox = QtWidgets.QCheckBox()
            checkbox.setStyleSheet("QCheckBox::indicator { width: 20px; height: 20px; }")
            h_layout.addWidget(checkbox)

            # Tên
            name_label = QtWidgets.QLabel(user['display_name'])
            name_label.setStyleSheet("font-size: 14px;")
            h_layout.addWidget(name_label)
            h_layout.addStretch()

            # Lưu user_id vào checkbox để lấy lại sau
            checkbox.setProperty("user_id", user['user_id'])

            widget.setLayout(h_layout)

            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def filter_users(self, text):
        filtered = [u for u in self.user_list if text.lower() in u['display_name'].lower()]
        self.populate_list(filtered)

    def handle_create(self):
        name = self.name_input.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên nhóm")
            return

        # Lấy danh sách ID đã check
        member_ids = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            checkbox = widget.findChild(QtWidgets.QCheckBox)
            if checkbox.isChecked():
                member_ids.append(checkbox.property("user_id"))

        if len(member_ids) < 2:
            QtWidgets.QMessageBox.warning(self, "Lỗi",
                                          "Nhóm cần tối thiểu 3 người (bao gồm bạn). Hãy chọn thêm ít nhất 2 người.")
            return

        self.selected_members = member_ids
        self.accept()

    def get_data(self):
        return self.name_input.text().strip(), self.selected_members