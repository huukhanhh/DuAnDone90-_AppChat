# client/views/create_group_dialog.py
from PySide6 import QtWidgets, QtCore, QtGui


class CreateGroupDialog(QtWidgets.QDialog):
    def __init__(self, parent, user_list, is_add_mode=False):
        super().__init__(parent)
        self.user_list = user_list
        self.is_add_mode = is_add_mode
        self.selected_members = []
        
        # Danh sách gốc đầy đủ để khôi phục sau khi lọc
        self.all_items_data = user_list

        self.setWindowTitle("Thêm thành viên" if is_add_mode else "Tạo nhóm mới")
        self.setFixedSize(450, 600)
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { color: #000000; font-size: 14px; }
            QLineEdit { 
                color: #000000; 
                border: 1px solid #e0e0e0; 
                border-radius: 20px; 
                padding: 10px 15px; 
                background-color: #f5f6f7;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #0084ff; background-color: #ffffff; }
            QListWidget { border: none; background-color: white; }
            QScrollBar:vertical { width: 8px; background: transparent; }
            QScrollBar::handle:vertical { background: #cccccc; border-radius: 4px; }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. Tên nhóm (Ẩn nếu là chế độ thêm)
        self.group_name_container = QtWidgets.QWidget()
        gn_layout = QtWidgets.QVBoxLayout(self.group_name_container)
        gn_layout.setContentsMargins(0,0,0,0)
        
        self.lbl_name = QtWidgets.QLabel("Tên nhóm")
        self.lbl_name.setStyleSheet("font-weight: bold; font-size: 16px;")
        gn_layout.addWidget(self.lbl_name)
        
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Nhập tên nhóm...")
        gn_layout.addWidget(self.name_input)
        
        layout.addWidget(self.group_name_container)

        if is_add_mode:
            self.group_name_container.hide()

        # 2. Tìm kiếm
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Tìm tên người dùng...")
        self.search_input.textChanged.connect(self.filter_users)
        layout.addWidget(self.search_input)

        # 3. Label List
        self.lbl_list = QtWidgets.QLabel("Danh sách thành viên")
        self.lbl_list.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(self.lbl_list)

        # 4. Danh sách User
        self.list_widget = QtWidgets.QListWidget()
        layout.addWidget(self.list_widget)

        # 5. Các nút bấm
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_cancel = QtWidgets.QPushButton("Hủy")
        self.btn_cancel.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton { 
                background-color: #f0f2f5; 
                color: #000000; 
                border-radius: 5px; 
                padding: 10px; 
                font-weight: 500;
            }
            QPushButton:hover { background-color: #e4e6eb; }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        btn_text = "Thêm" if is_add_mode else "Tạo nhóm"
        self.btn_create = QtWidgets.QPushButton(btn_text)
        self.btn_create.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_create.setStyleSheet("""
            QPushButton { 
                background-color: #0084ff; 
                color: white; 
                border-radius: 5px; 
                padding: 10px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0073e6; }
        """)
        self.btn_create.clicked.connect(self.handle_create)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_create)
        layout.addLayout(btn_layout)

        # Load users ban đầu
        self.populate_list(self.user_list)

    def populate_list(self, users):
        self.list_widget.clear()
        for user in users:
            item = QtWidgets.QListWidgetItem()
            
            # Widget tùy chỉnh
            widget = QtWidgets.QWidget()
            h_layout = QtWidgets.QHBoxLayout(widget)
            h_layout.setContentsMargins(5, 5, 5, 5)
            h_layout.setSpacing(15)

            # Avatar (Vòng tròn giữ chỗ hoặc mặc định)
            
            
            avatar_lbl = QtWidgets.QLabel()
            avatar_lbl.setFixedSize(40, 40)
            
            # Avatar chữ cái đơn giản nếu không có ảnh
            # Let's just use a color circle
            avatar_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: #e4e6eb;
                    border-radius: 20px;
                    color: #555;
                    font-weight: bold;
                    qproperty-alignment: AlignCenter;
                }}
            """)
            first_letter = user['display_name'][0].upper() if user['display_name'] else "?"
            avatar_lbl.setText(first_letter)
            h_layout.addWidget(avatar_lbl)

            # Name
            name_label = QtWidgets.QLabel(user['display_name'])
            name_label.setStyleSheet("font-size: 15px; font-weight: 500; color: #050505;")
            h_layout.addWidget(name_label)
            
            h_layout.addStretch()

            # Checkbox kiểu Zalo (Bên phải)
            checkbox = QtWidgets.QCheckBox()
            checkbox.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 22px;
                    height: 22px;
                    border-radius: 11px;
                    border: 2px solid #ccc;
                    background-color: transparent;
                }
                QCheckBox::indicator:checked {
                    background-color: #0084ff;
                    border-color: #0084ff;
                    image: url(none); /* Trong app thực tế dùng icon check */
                }
                   /* Hack cho checkmark: Dùng vòng tròn xanh đặc để báo hiệu đã chọn (đủ cho MVP). */
            """)
            h_layout.addWidget(checkbox)

            checkbox.setProperty("user_id", user['user_id'])

            widget.setLayout(h_layout)
            item.setSizeHint(widget.sizeHint())
            
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def filter_users(self, text):
        # Lọc từ TẤT CẢ items
        filtered = [u for u in self.all_items_data if text.lower() in u['display_name'].lower()]
        self.populate_list(filtered)

    def handle_create(self):
        # Validate tên nếu KHÔNG phải chế độ thêm
        if not self.is_add_mode:
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

        # Validation logic
        min_members = 1 if self.is_add_mode else 2
        warn_msg = "Vui lòng chọn ít nhất 1 thành viên." if self.is_add_mode else "Nhóm cần tối thiểu 3 người (bao gồm bạn). Hãy chọn thêm ít nhất 2 người."
        
        if len(member_ids) < min_members:
             QtWidgets.QMessageBox.warning(self, "Lỗi", warn_msg)
             return

        self.selected_members = member_ids
        self.accept()

    def get_data(self):
        return self.name_input.text().strip(), self.selected_members