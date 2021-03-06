"""
This file is part of Giswater 2.0
The program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.
"""

# -*- coding: utf-8 -*-
from PyQt4.QtGui import QDateEdit, QLineEdit, QDoubleValidator, QTableView, QAbstractItemView
from PyQt4.QtSql import QSqlTableModel
from PyQt4.QtCore import Qt

import os
import sys
import operator
from functools import partial

plugin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(plugin_path)
import utils_giswater
                   
from actions.manage_new_psector import ManageNewPsector
from ui.psector_management import Psector_management           
from ui.plan_estimate_result_new import EstimateResultNew
from ui.plan_estimate_result_selector import EstimateResultSelector
from ui.plan_estimate_result_manager import EstimateResultManager                             
from ui.multirow_selector import Multirow_selector                              
from parent import ParentAction


class Master(ParentAction):

    def __init__(self, iface, settings, controller, plugin_dir):
        """ Class to control toolbar 'master' """
        self.config_dict = {}
        ParentAction.__init__(self, iface, settings, controller, plugin_dir)
        self.manage_new_psector = ManageNewPsector(iface, settings, controller, plugin_dir)


    def set_project_type(self, project_type):
        self.project_type = project_type


    def master_new_psector(self, psector_id=None):
        """ Button 45: New psector """
        self.manage_new_psector.new_psector(psector_id, 'plan')


    def master_psector_mangement(self):
        """ Button 46: Psector management """

        # Create the dialog and signals
        self.dlg = Psector_management()
        utils_giswater.setDialog(self.dlg)
        self.load_settings(self.dlg)
        table_name = "plan_psector"
        column_id = "psector_id"

        # Tables
        qtbl_psm = self.dlg.findChild(QTableView, "tbl_psm")
        qtbl_psm.setSelectionBehavior(QAbstractItemView.SelectRows)

        # Set signals
        self.dlg.btn_cancel.pressed.connect(self.close_dialog)
        self.dlg.rejected.connect(self.close_dialog)
        self.dlg.btn_delete.clicked.connect(partial(self.multi_rows_delete, qtbl_psm, table_name, column_id))
        self.dlg.btn_update_psector.clicked.connect(partial(self.update_current_psector, qtbl_psm))
        self.dlg.txt_name.textChanged.connect(partial(self.filter_by_text, qtbl_psm, self.dlg.txt_name, "plan_psector"))
        self.dlg.tbl_psm.doubleClicked.connect(partial(self.charge_psector, qtbl_psm))
        self.fill_table_psector(qtbl_psm, table_name)
        self.set_table_columns(qtbl_psm, table_name)
        self.set_label_current_psector()

        # Open form
        self.dlg.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.open_dialog(self.dlg, dlg_name="psector_management")



    def update_current_psector(self, qtbl_psm):
      
        selected_list = qtbl_psm.selectionModel().selectedRows()
        if len(selected_list) == 0:
            message = "Any record selected"
            self.controller.show_warning(message)
            return
        row = selected_list[0].row()
        psector_id = qtbl_psm.model().record(row).value("psector_id")
        aux_widget = QLineEdit()
        aux_widget.setText(str(psector_id))
        self.upsert_config_param_user(aux_widget, "psector_vdefault")

        message = "Values has been updated"
        self.controller.show_info(message)

        self.fill_table(qtbl_psm, "plan_psector")
        #self.set_table_columns(qtbl_psm, "plan_psector")
        self.set_label_current_psector()
        self.open_dialog(self.dlg)


    def upsert_config_param_user(self, widget, parameter):
        """ Insert or update values in tables with current_user control """

        tablename = "config_param_user"
        sql = ("SELECT * FROM " + self.schema_name + "." + tablename + ""
               " WHERE cur_user = current_user")
        rows = self.controller.get_rows(sql)
        exist_param = False
        if type(widget) != QDateEdit:
            if utils_giswater.getWidgetText(widget) != "":
                for row in rows:
                    if row[1] == parameter:
                        exist_param = True
                if exist_param:
                    sql = "UPDATE " + self.schema_name + "." + tablename + " SET value = "
                    if widget.objectName() != 'state_vdefault':
                        sql += ("'" + utils_giswater.getWidgetText(widget) + "'"
                                " WHERE cur_user = current_user AND parameter = '" + parameter + "'")
                    else:
                        sql += ("(SELECT id FROM " + self.schema_name + ".value_state"
                                " WHERE name = '" + utils_giswater.getWidgetText(widget) + "')"
                                " WHERE cur_user = current_user AND parameter = 'state_vdefault'")
                else:
                    sql = 'INSERT INTO ' + self.schema_name + '.' + tablename + '(parameter, value, cur_user)'
                    if widget.objectName() != 'state_vdefault':
                        sql += " VALUES ('" + parameter + "', '" + utils_giswater.getWidgetText(widget) + "', current_user)"
                    else:
                        sql += (" VALUES ('" + parameter + "',"
                                " (SELECT id FROM " + self.schema_name + ".value_state"
                                " WHERE name = '" + utils_giswater.getWidgetText(widget) + "'), current_user)")
        else:
            for row in rows:
                if row[1] == parameter:
                    exist_param = True
            _date = widget.dateTime().toString('yyyy-MM-dd')
            if exist_param:
                sql = ("UPDATE " + self.schema_name + "." + tablename + ""
                       " SET value = '" + str(_date) + "'"
                       " WHERE cur_user = current_user AND parameter = '" + parameter + "'")
            else:
                sql = ("INSERT INTO " + self.schema_name + "." + tablename + "(parameter, value, cur_user)"
                       " VALUES ('" + parameter + "', '" + _date + "', current_user);")
        self.controller.execute_sql(sql)


    def filter_by_text(self, table, widget_txt, tablename):

        result_select = utils_giswater.getWidgetText(widget_txt)
        if result_select != 'null':
            expr = " name ILIKE '%" + result_select + "%'"
            # Refresh model with selected filter
            table.model().setFilter(expr)
            table.model().select()
        else:
            self.fill_table(table, tablename)


    def charge_psector(self, qtbl_psm):

        selected_list = qtbl_psm.selectionModel().selectedRows()
        if len(selected_list) == 0:
            message = "Any record selected"
            self.controller.show_warning(message)
            return
        row = selected_list[0].row()
        psector_id = qtbl_psm.model().record(row).value("psector_id")
        self.close_dialog()
        self.master_new_psector(psector_id)


    def multi_rows_delete(self, widget, table_name, column_id):
        """ Delete selected elements of the table
        :param QTableView widget: origin
        :param table_name: table origin
        :param column_id: Refers to the id of the source table
        """

        # Get selected rows
        selected_list = widget.selectionModel().selectedRows()
        if len(selected_list) == 0:
            message = "Any record selected"
            self.controller.show_warning(message)
            return

        inf_text = ""
        list_id = ""
        for i in range(0, len(selected_list)):
            row = selected_list[i].row()
            id_ = widget.model().record(row).value(str(column_id))
            inf_text += str(id_)+", "
            list_id = list_id+"'"+str(id_)+"', "
        inf_text = inf_text[:-2]
        list_id = list_id[:-2]
        message = "Are you sure you want to delete these records?"
        answer = self.controller.ask_question(message, "Delete records", inf_text)

        if answer:
            sql = ("DELETE FROM " + self.schema_name + "." + table_name + ""
                   " WHERE " + column_id + " IN (" + list_id + ")")
            self.controller.execute_sql(sql)
            widget.model().select()
            sql = ("SELECT value FROM " + self.schema_name + ".config_param_user "
                   " WHERE parameter = 'psector_vdefault' AND value IN (" + list_id + ")")
            row = self.controller.get_row(sql)
            if row is not None:
                sql = ("DELETE FROM " + self.schema_name + ".config_param_user "
                       " WHERE parameter = 'psector_vdefault' AND value ='" + row[0] + "'")
                self.controller.execute_sql(sql)
                utils_giswater.setWidgetText('lbl_vdefault_psector', '')


    def master_psector_selector(self):
        """ Button 47: Psector selector """

        # Create the dialog and signals
        self.dlg = Multirow_selector()
        utils_giswater.setDialog(self.dlg)
        self.load_settings(self.dlg)
        self.dlg.btn_ok.pressed.connect(self.close_dialog)
        self.dlg.setWindowTitle("Psector")
        tableleft = "plan_psector"
        tableright = "selector_psector"
        field_id_left = "psector_id"
        field_id_right = "psector_id"
        self.multi_row_selector(self.dlg, tableleft, tableright, field_id_left, field_id_right)
        self.open_dialog(self.dlg, dlg_name="multirow_selector", maximize_button=False)

        
    def master_estimate_result_new(self, tablename=None, result_id=None, index=0):
        """ Button 38: New estimate result """

        # Create dialog 
        self.dlg = EstimateResultNew()
        utils_giswater.setDialog(self.dlg)
        self.load_settings(self.dlg)

        # Set signals
        self.dlg.btn_calculate.clicked.connect(self.master_estimate_result_new_calculate)
        self.dlg.btn_close.clicked.connect(self.close_dialog)
        self.dlg.prices_coefficient.setValidator(QDoubleValidator())

        self.populate_cmb_result_type(self.dlg.cmb_result_type, 'plan_result_type', False)

        if result_id != 0 and result_id:         
            sql = ("SELECT * FROM " + self.schema_name + "." + tablename + " "
                   " WHERE result_id = '" + str(result_id) + "' AND current_user = cur_user")
            row = self.controller.get_row(sql)
            if row is None:
                message = "Any record found for current user in table"
                self.controller.show_warning(message, parameter='plan_result_cat')
                return

            utils_giswater.setWidgetText(self.dlg.result_name, row['result_id'])
            self.dlg.cmb_result_type.setCurrentIndex(index)
            utils_giswater.setWidgetText(self.dlg.prices_coefficient, row['network_price_coeff'])
            utils_giswater.setWidgetText(self.dlg.observ, row['descript'])

            self.dlg.result_name.setEnabled(False)
            self.dlg.cmb_result_type.setEnabled(False)
            self.dlg.prices_coefficient.setEnabled(False)
            self.dlg.observ.setEnabled(False)

        # Manage i18n of the form and open it
        self.controller.translate_form(self.dlg, 'estimate_result_new')

        self.open_dialog(self.dlg, dlg_name="plan_estimate_result_new", maximize_button=False)


    def populate_cmb_result_type(self, combo, table_name, allow_nulls=True):

        sql = ("SELECT id, name"
                " FROM " + self.schema_name + "." + table_name + ""
                " ORDER BY name")
        rows = self.controller.get_rows(sql)
        if not rows:
            return
        
        combo.blockSignals(True)
        combo.clear()
        if allow_nulls:
            combo.addItem("", "")
        records_sorted = sorted(rows, key=operator.itemgetter(1))
        for record in records_sorted:
            combo.addItem(str(record[1]), record)
        combo.blockSignals(False)


    def master_estimate_result_new_calculate(self):
        """ Execute function 'gw_fct_plan_estimate_result' """

        # Get values from form
        result_name = utils_giswater.getWidgetText("result_name")
        combo = utils_giswater.getWidget("cmb_result_type")
        elem = combo.itemData(combo.currentIndex())
        result_type = str(elem[0])
        coefficient = utils_giswater.getWidgetText("prices_coefficient")
        observ = utils_giswater.getWidgetText("observ")

        if result_name == 'null':
            message = "Please, introduce a result name"
            self.controller.show_warning(message)
            return
        if coefficient == 'null':
            message = "Please, introduce a coefficient value"
            self.controller.show_warning(message)  
            return          
        
        # Check data executing function 'gw_fct_epa_audit_check_data'
        sql = "SELECT " + self.schema_name + ".gw_fct_plan_audit_check_data(" + str(result_type) + ");"
        row = self.controller.get_row(sql, log_sql=True)
        if not row:
            return
        
        if row[0] > 0:
            msg = ("It is not possible to execute the economic result."
                   "There are errors on your project. Review it!")
            if result_type == 1:
                fprocesscat_id = 15
            else:
                fprocesscat_id = 16
            sql_details = ("SELECT table_id, column_id, error_message"
                           " FROM audit_check_data"
                           " WHERE fprocesscat_id = " + str(fprocesscat_id) + " AND enabled is false")
            inf_text = "For more details execute query:\n" + sql_details
            title = "Execute epa model"
            self.controller.show_info_box(msg, title, inf_text, parameter=row[0])
            return
        
        # Execute function 'gw_fct_plan_result'
        sql = ("SELECT " + self.schema_name + ".gw_fct_plan_result('"
               + result_name + "', " + result_type + ", '" + coefficient + "', '" + observ + "');")
        status = self.controller.execute_sql(sql)
        if status:
            message = "Values has been updated"
            self.controller.show_info(message)

        # Refresh canvas and close dialog
        self.iface.mapCanvas().refreshAllLayers()
        self.close_dialog()


    def master_estimate_result_selector(self):
        """ Button 49: Estimate result selector """

        # Create dialog 
        self.dlg = EstimateResultSelector()
        utils_giswater.setDialog(self.dlg)
        self.load_settings(self.dlg)
        
        # Populate combo
        self.populate_combo(self.dlg.rpt_selector_result_id, 'plan_result_selector')

        # Set current value
        table_name = "om_result_cat"
        sql = ("SELECT name FROM " + self.schema_name + "." + table_name + " "
               " WHERE cur_user = current_user AND result_type = 1 AND result_id = (SELECT result_id FROM "
               + self.schema_name + ".plan_result_selector)")
        row = self.controller.get_row(sql)
        if row:
            utils_giswater.setWidgetText(self.dlg.rpt_selector_result_id, str(row[0]))
            
        # Set signals
        self.dlg.btn_accept.clicked.connect(partial(self.master_estimate_result_selector_accept))
        self.dlg.btn_cancel.clicked.connect(self.close_dialog)
        
        # Manage i18n of the form and open it
        self.controller.translate_form(self.dlg, 'estimate_result_selector')
        self.open_dialog(self.dlg, dlg_name="plan_estimate_result_selector",maximize_button=False)


    def populate_combo(self, combo, table_result):

        table_name = "om_result_cat"
        sql = ("SELECT name, result_id"
               " FROM " + self.schema_name + "." + table_name + " "
               " WHERE cur_user = current_user"
               " AND result_type = 1"
               " ORDER BY name")
        rows = self.controller.get_rows(sql)
        if not rows:
            return

        combo.blockSignals(True)
        combo.clear()
        records_sorted = sorted(rows, key=operator.itemgetter(1))
        for record in records_sorted:
            combo.addItem(str(record[0]), record)
        combo.blockSignals(False)
        
        # Check if table exists
        if not self.controller.check_table(table_result):
            message = "Table not found"
            self.controller.show_warning(message, parameter=table_result)
            return
        
        sql = ("SELECT result_id FROM " + self.schema_name + "." + table_result + " "
               " WHERE cur_user = current_user")
        row = self.controller.get_row(sql)
        if row:
            utils_giswater.setSelectedItem(combo, str(row[0]))


    def upsert(self, combo, tablename):
        
        # Check if table exists
        if not self.controller.check_table(tablename):
            message = "Table not found"
            self.controller.show_warning(message, parameter=tablename)
            return
                
        result_id = utils_giswater.get_item_data(combo, 1)             
        sql = ("DELETE FROM " + self.schema_name + "." + tablename + " WHERE current_user = cur_user;"
               "\nINSERT INTO " + self.schema_name + "." + tablename + " (result_id, cur_user)"
               " VALUES(" + str(result_id) + ", current_user);")
        status = self.controller.execute_sql(sql)
        if status:
            message = "Values has been updated"
            self.controller.show_info(message)

        # Refresh canvas
        self.iface.mapCanvas().refreshAllLayers()
        self.close_dialog(self.dlg)
        

    def master_estimate_result_selector_accept(self):
        """ Update value of table 'plan_result_selector' """
        
        self.upsert(self.dlg.rpt_selector_result_id, 'plan_result_selector')


    def master_estimate_result_manager(self):
        """ Button 50: Plan estimate result manager """

        # Create the dialog and signals
        self.dlg_merm = EstimateResultManager()
        utils_giswater.setDialog(self.dlg_merm)
        self.load_settings(self.dlg_merm)
        
        #TODO activar este boton cuando sea necesario
        self.dlg_merm.btn_delete.setVisible(False)

        # Tables
        tablename = 'om_result_cat'
        self.tbl_om_result_cat = self.dlg_merm.findChild(QTableView, "tbl_om_result_cat")
        self.tbl_om_result_cat.setSelectionBehavior(QAbstractItemView.SelectRows)

        # Set signals
        self.dlg_merm.tbl_om_result_cat.doubleClicked.connect(partial(self.charge_plan_estimate_result, self.dlg_merm))
        self.dlg_merm.btn_cancel.pressed.connect(partial(self.close_dialog, self.dlg_merm))
        self.dlg_merm.rejected.connect(partial(self.close_dialog, self.dlg_merm))
        self.dlg_merm.btn_delete.clicked.connect(partial(self.delete_merm, self.dlg_merm))
        self.dlg_merm.txt_name.textChanged.connect(partial(self.filter_merm, self.dlg_merm, tablename))

        set_edit_strategy = QSqlTableModel.OnManualSubmit
        self.fill_table(self.tbl_om_result_cat, tablename, set_edit_strategy)
        #self.set_table_columns(self.tbl_om_result_cat, tablename)

        # Open form
        self.dlg_merm.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.open_dialog(self.dlg_merm,dlg_name="plan_estimate_result_manager")


    def charge_plan_estimate_result(self, dialog):
        """ Send selected plan to 'plan_estimate_result_new.ui' """
        
        selected_list = dialog.tbl_om_result_cat.selectionModel().selectedRows()
        if len(selected_list) == 0:
            message = "Any record selected"
            self.controller.show_warning(message)
            return
        
        row = selected_list[0].row()
        result_id = dialog.tbl_om_result_cat.model().record(row).value("result_id")
        self.close_dialog(dialog)
        self.master_estimate_result_new('om_result_cat', result_id, 0)


    def delete_merm(self, dialog):
        """ Delete selected row from 'master_estimate_result_manager' dialog from selected tab """
        
        self.multi_rows_delete(dialog.tbl_om_result_cat, 'plan_result_cat', 'result_id')


    def filter_merm(self, dialog, tablename):
        """ Filter rows from 'master_estimate_result_manager' dialog from selected tab """
        
        self.filter_by_text(dialog.tbl_om_result_cat, dialog.txt_name, tablename)
            
