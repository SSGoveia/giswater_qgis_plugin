"""
This file is part of Giswater 2.0
The program is free software: you can redistribute it and/or modify it under the terms of the GNU 
General Public License as published by the Free Software Foundation, either version 3 of the License, 
or (at your option) any later version.
"""

# -*- coding: utf-8 -*-
from PyQt4.QtGui import QPushButton, QTableView, QTabWidget, QAction, QComboBox, QLineEdit, QAbstractItemView, QColor
from PyQt4.QtCore import QPoint, Qt
from PyQt4.QtSql import QSqlTableModel
from qgis.core import QgsExpression, QgsFeatureRequest, QgsPoint
from qgis.gui import QgsMapCanvasSnapper, QgsMapToolEmitPoint, QgsVertexMarker

from functools import partial
from init.thread import Thread

import utils_giswater
from parent_init import ParentDialog
from map_tools.snapping_utils import SnappingConfigManager


def formOpen(dialog, layer, feature):
    """ Function called when a connec is identified in the map """
    
    global feature_dialog
    utils_giswater.setDialog(dialog)
    # Create class to manage Feature Form interaction  
    feature_dialog = ManNodeDialog(dialog, layer, feature)
    init_config()

    
def init_config():

    # Manage 'node_type'
    node_type = utils_giswater.getWidgetText("node_type") 
    utils_giswater.setSelectedItem("node_type", node_type)
     
    # Manage 'nodecat_id'
    nodecat_id = utils_giswater.getWidgetText("nodecat_id") 
    utils_giswater.setSelectedItem("nodecat_id", nodecat_id)      
    
     
class ManNodeDialog(ParentDialog):
    
    def __init__(self, dialog, layer, feature):
        """ Constructor class """
        
        self.geom_type = "node"        
        self.field_id = "node_id"        
        self.id = utils_giswater.getWidgetText(self.field_id, False)          
        super(ManNodeDialog, self).__init__(dialog, layer, feature)      
        self.init_config_form()
        self.controller.manage_translation('ud_man_node', dialog) 
        if dialog.parent():
            dialog.parent().setFixedSize(625, 660)
            
        
    def init_config_form(self):
        """ Custom form initial configuration """
              
        # Define class variables
        self.filter = self.field_id + " = '" + str(self.id) + "'"                    
        
        # Get widget controls      
        self.tab_main = self.dialog.findChild(QTabWidget, "tab_main")  
        self.tbl_element = self.dialog.findChild(QTableView, "tbl_element")   
        self.tbl_document = self.dialog.findChild(QTableView, "tbl_document")  
        self.tbl_event_element = self.dialog.findChild(QTableView, "tbl_event_element") 
        self.tbl_event = self.dialog.findChild(QTableView, "tbl_event_node") 
        self.tbl_scada = self.dialog.findChild(QTableView, "tbl_scada") 
        self.tbl_scada_value = self.dialog.findChild(QTableView, "tbl_scada_value") 
        self.tbl_costs = self.dialog.findChild(QTableView, "tbl_masterplan")
        self.nodecat_id = self.dialog.findChild(QLineEdit, 'nodecat_id')
        self.node_type = self.dialog.findChild(QComboBox, 'node_type')
        state_type = self.dialog.findChild(QComboBox, 'state_type')
        dma_id = self.dialog.findChild(QComboBox, 'dma_id')

        # Tables
        self.tbl_upstream = self.dialog.findChild(QTableView, "tbl_upstream")
        self.tbl_upstream.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_downstream = self.dialog.findChild(QTableView, "tbl_downstream")
        self.tbl_downstream.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.dialog.findChild(QPushButton, "btn_catalog").clicked.connect(partial(self.catalog, 'ud', 'node'))

        self.tbl_upstream.doubleClicked.connect(partial(self.open_up_down_stream, self.tbl_upstream))
        self.tbl_downstream.doubleClicked.connect(partial(self.open_up_down_stream, self.tbl_downstream))

        feature = self.feature
        layer = self.iface.activeLayer()
        
        # Toolbar actions
        action = self.dialog.findChild(QAction, "actionEnabled")
        action.setChecked(layer.isEditable())
        self.dialog.findChild(QAction, "actionCopyPaste").setEnabled(layer.isEditable())
        self.dialog.findChild(QAction, "actionRotation").setEnabled(layer.isEditable())
        self.dialog.findChild(QAction, "actionZoom").triggered.connect(partial(self.action_zoom_in, feature, self.canvas, layer))
        self.dialog.findChild(QAction, "actionCentered").triggered.connect(partial(self.action_centered,feature, self.canvas, layer))
        self.dialog.findChild(QAction, "actionEnabled").triggered.connect(partial(self.action_enabled, action, layer))
        self.dialog.findChild(QAction, "actionZoomOut").triggered.connect(partial(self.action_zoom_out, feature, self.canvas, layer))
        self.dialog.findChild(QAction, "actionRotation").triggered.connect(self.action_rotation)        
        self.dialog.findChild(QAction, "actionCopyPaste").triggered.connect(partial(self.action_copy_paste, self.geom_type))
        self.dialog.findChild(QAction, "actionLink").triggered.connect(partial(self.check_link, True))
        self.dialog.findChild(QAction, "actionHelp").triggered.connect(partial(self.action_help, 'ud', 'node'))

        # Manage custom fields   
        cat_feature_id = utils_giswater.getWidgetText(self.node_type)        
        tab_custom_fields = 1
        self.manage_custom_fields(cat_feature_id, tab_custom_fields)
        
        # Manage tab 'Scada'
        self.manage_tab_scada()        
        
        # Check if exist URL from field 'link' in main tab
        self.check_link()

        # Check topology for new features
        continue_insert = True        
        node_over_node = True     
        check_topology_node = self.controller.plugin_settings_value("check_topology_node", "0")
        check_topology_arc = self.controller.plugin_settings_value("check_topology_arc", "0")
         
        # Check if feature has geometry object
        geometry = self.feature.geometry()   
        if geometry:
            self.controller.log_info("check")
            if self.id.upper() == 'NULL' and check_topology_node == "0":
                self.get_topology_parameters()
                (continue_insert, node_over_node) = self.check_topology_node()    
            
            if continue_insert and not node_over_node:           
                if self.id.upper() == 'NULL' and check_topology_arc == "0":
                    self.check_topology_arc()           
            
            # Create thread    
            thread1 = Thread(self, self.controller, 3)
            thread1.start()  

        self.filter = "node_id = '" + str(self.id) + "'"
        table_name = self.controller.schema_name + ".v_ui_node_x_connection_upstream"
        self.fill_table(self.tbl_upstream, table_name, self.filter)
        self.set_configuration(self.tbl_upstream, "v_ui_node_x_connection_upstream")

        table_name = self.controller.schema_name + ".v_ui_node_x_connection_downstream"
        self.fill_table(self.tbl_downstream, table_name, self.filter)
        self.set_configuration(self.tbl_downstream, "v_ui_node_x_connection_downstream")

        # Manage tab signal
        self.tab_connections_loaded = False           
        self.tab_element_loaded = False        
        self.tab_document_loaded = False        
        self.tab_om_loaded = False        
        self.tab_scada_loaded = False        
        self.tab_cost_loaded = False        
        self.tab_main.currentChanged.connect(self.tab_activation)

        # Load default settings
        widget_id = self.dialog.findChild(QLineEdit, 'node_id')
        if utils_giswater.getWidgetText(widget_id).lower() == 'null':
            self.load_default()
            self.load_type_default("nodecat_id", "nodecat_vdefault")

        self.load_state_type(state_type, self.geom_type)
        self.load_dma(dma_id, self.geom_type)


    def open_up_down_stream(self, qtable):
        """ Open selected node from @qtable """
        
        selected_list = qtable.selectionModel().selectedRows()
        if len(selected_list) == 0:
            message = "Any record selected"
            self.controller.show_warning(message)
            return
        
        row = selected_list[0].row()
        feature_id = qtable.model().record(row).value("feature_id")
        featurecat_id = qtable.model().record(row).value("featurecat_id")
        
        # Get sys_feature_cat.id from cat_feature.id
        sql = ("SELECT sys_feature_cat.id FROM " + self.controller.schema_name + ".cat_feature"
               " INNER JOIN " + self.controller.schema_name + ".sys_feature_cat ON cat_feature.system_id = sys_feature_cat.id"
               " WHERE cat_feature.id = '" + featurecat_id + "'")
        row = self.controller.get_row(sql)
        if not row:
            return
        
        layer = self.get_layer(row[0])            
        if layer:
            field_id = self.controller.get_layer_primary_key(layer)             
            aux = "\"" + field_id+ "\" = "
            aux += "'" + str(feature_id) + "'"
            expr = QgsExpression(aux)                  
            if expr.hasParserError():
                message = "Expression Error"
                self.controller.show_warning(message, parameter=expr.parserErrorString())
                return    
                                                      
            it = layer.getFeatures(QgsFeatureRequest(expr))
            features = [i for i in it]                                
            if features != []:                                
                self.iface.openFeatureForm(layer, features[0])
        else:
            message = "Layer not found"
            self.controller.show_warning(message, parameter=row[0])


    def get_topology_parameters(self):
        """ Get parameters 'node_proximity' and 'node2arc' from config table """
        
        self.node_proximity = 0.5
        self.node2arc = 0.5
        sql = "SELECT node_proximity, node2arc FROM " + self.schema_name + ".config"
        row = self.controller.get_row(sql)
        if row:
            self.node_proximity = row['node_proximity'] 
            self.node2arc = row['node2arc']   
            
            
    def check_topology_arc(self):
        """ Check topology: Inserted node is over an existing arc? """
       
        # Initialize plugin parameters
        self.controller.plugin_settings_set_value("check_topology_arc", "0")       
        self.controller.plugin_settings_set_value("close_dlg", "0")
                        
        # Get selected srid and coordinates. Set SQL to check topology  
        srid = self.controller.plugin_settings_value('srid')
        point = self.feature.geometry().asPoint()
        node_geom = "ST_SetSRID(ST_Point(" + str(point.x()) + ", " + str(point.y()) + "), " + str(srid) + ")"
    
        sql = ("SELECT arc_id, state FROM " + self.schema_name + ".v_edit_arc"
               " WHERE ST_DWithin(" + node_geom + ", v_edit_arc.the_geom, " + str(self.node2arc) + ")"
               " ORDER BY ST_Distance(v_edit_arc.the_geom, " + node_geom + ")"
               " LIMIT 1")
        row = self.controller.get_row(sql)
        if row:
            msg = ("We have detected you are trying to divide an arc with state " + str(row['state']) + ""
                   "\nRemember that:"
                   "\n\nIn case of arc has state 0, you are allowed to insert a new node, because state 0 has not topology rules, and as a result arc will not be broken."
                   "\nIn case of arc has state 1, only nodes with state=1 can be part of node1 or node2 from arc. If the new node has state 0 or state 2 arc will be broken."
                   "\nIn case of arc has state 2, nodes with state 1 or state 2 are enabled. If the new node has state 0 arc will not be broken"
                   "\n\nWould you like to continue?")         
            answer = self.controller.ask_question(msg, "Divide intersected arc?")
            if answer:      
                self.controller.plugin_settings_set_value("check_topology_arc", "1")
            else:
                self.controller.plugin_settings_set_value("close_dlg", "1")


    def check_topology_node(self):
        """ Check topology: Inserted node is over an existing node? """
       
        node_over_node = False
        continue_insert = True
        
        # Initialize plugin parameters
        self.controller.plugin_settings_set_value("check_topology_node", "0")       
        self.controller.plugin_settings_set_value("close_dlg", "0")
                
        # Get selected srid and coordinates. Set SQL to check topology  
        srid = self.controller.plugin_settings_value('srid')
        point = self.feature.geometry().asPoint()  
        node_geom = "ST_SetSRID(ST_Point(" + str(point.x()) + ", " + str(point.y()) + "), " + str(srid) + ")"
                     
        sql = ("SELECT node_id, state FROM " + self.schema_name + ".v_edit_node" 
               " WHERE ST_Intersects(ST_Buffer(" + node_geom + ", " + str(self.node_proximity) + "), the_geom)"
               " ORDER BY ST_Distance(" + node_geom + ", the_geom)"
               " LIMIT 1")           
        row = self.controller.get_row(sql)
        if row:
            node_over_node = True
            msg = ("We have detected you are trying to insert one node over another node with state " + str(row['state']) + ""
                   "\nRemember that:"
                   "\n\nIn case of old or new node has state 0, you are allowed to insert new one, because state 0 has not topology rules."
                   "\nIn the rest of cases, remember that the state topology rules of Giswater only enables one node with the same state at the same position."
                   "\n\nWould you like to continue?")    
            answer = self.controller.ask_question(msg, "Insert node over node?")
            if answer:      
                self.controller.plugin_settings_set_value("check_topology_node", "1")
            else:
                self.controller.plugin_settings_set_value("close_dlg", "1")
                continue_insert = False
        
        return (continue_insert, node_over_node)    
    
    
    def action_rotation(self):
    
        # Set map tool emit point and signals    
        self.emit_point = QgsMapToolEmitPoint(self.canvas)
        self.canvas.setMapTool(self.emit_point)
        self.snapper = QgsMapCanvasSnapper(self.canvas)
        self.canvas.xyCoordinates.connect(self.action_rotation_mouse_move)
        self.emit_point.canvasClicked.connect(self.action_rotation_canvas_clicked)
        
        # Store user snapping configuration
        self.snapper_manager = SnappingConfigManager(self.iface)
        self.snapper_manager.store_snapping_options()

        # Clear snapping
        self.snapper_manager.clear_snapping()

        # Set snapping 
        layer = self.controller.get_layer_by_tablename("v_edit_arc")
        self.snapper_manager.snap_to_layer(layer)             
        layer = self.controller.get_layer_by_tablename("v_edit_connec")
        self.snapper_manager.snap_to_layer(layer)             
        layer = self.controller.get_layer_by_tablename("v_edit_node")
        self.snapper_manager.snap_to_layer(layer)     
        
        # Set marker
        color = QColor(255, 100, 255)
        self.vertex_marker = QgsVertexMarker(self.canvas)
        self.vertex_marker.setIconType(QgsVertexMarker.ICON_CROSS)
        self.vertex_marker.setColor(color)
        self.vertex_marker.setIconSize(15)
        self.vertex_marker.setPenWidth(3)                     
        
        
    def action_rotation_mouse_move(self, point):
        """ Slot function when mouse is moved in the canvas. 
            Add marker if any feature is snapped 
        """
         
        # Hide marker and get coordinates
        self.vertex_marker.hide()
        map_point = self.canvas.getCoordinateTransform().transform(point)
        x = map_point.x()
        y = map_point.y()
        event_point = QPoint(x, y)

        # Snapping
        (retval, result) = self.snapper.snapToBackgroundLayers(event_point)  # @UnusedVariable

        if not result:
            return
            
        # Check snapped features
        for snapped_point in result:              
            point = QgsPoint(snapped_point.snappedVertex)
            self.vertex_marker.setCenter(point)
            self.vertex_marker.show()
            break 
        
                
    def action_rotation_canvas_clicked(self, point, btn):
        
        if btn == Qt.RightButton:
            self.disable_rotation() 
            return           
        
        viewname = self.controller.get_layer_source_table_name(self.layer) 
        sql = ("SELECT ST_X(the_geom), ST_Y(the_geom)"
               " FROM " + self.schema_name + "." + viewname + ""
               " WHERE node_id = '" + self.id + "'")
        row = self.controller.get_row(sql)
        if row:
            existing_point_x = row[0]
            existing_point_y = row[1]
             
        sql = ("UPDATE " + self.schema_name + ".node"
               " SET hemisphere = (SELECT degrees(ST_Azimuth(ST_Point(" + str(existing_point_x) + ", " + str(existing_point_y) + "), "
               " ST_Point(" + str(point.x()) + ", " + str(point.y()) + "))))"
               " WHERE node_id = '" + str(self.id) + "'")
        status = self.controller.execute_sql(sql)
        if not status:
            self.disable_rotation()
            return

        sql = ("SELECT degrees(ST_Azimuth(ST_Point(" + str(existing_point_x) + ", " + str(existing_point_y) + "),"
               " ST_Point( " + str(point.x()) + ", " + str(point.y()) + ")))")
        row = self.controller.get_row(sql)
        if row:
            utils_giswater.setWidgetText("hemisphere" , str(row[0]))
            message = "Hemisphere of the node has been updated. Value is"
            self.controller.show_info(message, parameter=str(row[0]))
   
        self.disable_rotation()
               
   
    def disable_rotation(self):
        """ Disable actionRotation and set action 'Identify' """
        
        action_widget = self.dialog.findChild(QAction, "actionRotation")
        if action_widget:
            action_widget.setChecked(False) 
          
        try:  
            self.snapper_manager.recover_snapping_options()            
            self.vertex_marker.hide()           
            self.set_action_identify()
            self.canvas.xyCoordinates.disconnect()        
            self.emit_point.canvasClicked.disconnect()            
        except:
            pass


    def tab_activation(self):
        """ Call functions depend on tab selection """
        
        # Get index of selected tab
        index_tab = self.tab_main.currentIndex()
        
        # Tab 'Connections'    
        if index_tab == (2 - self.tabs_removed) and not self.tab_connections_loaded:           
            self.fill_tab_connections()           
            self.tab_connections_loaded = True                
            
        # Tab 'Element'    
        elif index_tab == (3 - self.tabs_removed) and not self.tab_element_loaded:
            self.fill_tab_element()           
            self.tab_element_loaded = True 
            
        # Tab 'Document'    
        elif index_tab == (4 - self.tabs_removed) and not self.tab_document_loaded:
            self.fill_tab_document()           
            self.tab_document_loaded = True 
            
        # Tab 'O&M'    
        elif index_tab == (5 - self.tabs_removed) and not self.tab_om_loaded:
            self.fill_tab_om()           
            self.tab_om_loaded = True 
                      
        # Tab 'Scada'    
        elif index_tab == (6 - self.tabs_removed) and not self.tab_scada_loaded:
            self.fill_tab_scada()           
            self.tab_scada_loaded = True   
              
        # Tab 'Cost'    
        elif index_tab == (7 - self.tabs_removed) and not self.tab_cost_loaded:
            self.fill_tab_cost()           
            self.tab_cost_loaded = True     
            
        
    def fill_tab_connections(self):
        """ Fill tab 'Connections' """            
            
        self.fill_tables(self.tbl_upstream, "v_ui_node_x_connection_upstream")
        self.fill_tables(self.tbl_downstream, "v_ui_node_x_connection_downstream")
        
        
    def fill_tab_element(self):
        """ Fill tab 'Element' """
        
        table_element = "v_ui_element_x_node" 
        self.fill_tbl_element_man(self.tbl_element, table_element, self.filter)
        self.set_configuration(self.tbl_element, table_element)
                        

    def fill_tab_document(self):
        """ Fill tab 'Document' """
        
        table_document = "v_ui_doc_x_node"       
        self.fill_tbl_document_man(self.tbl_document, table_document, self.filter)
        self.set_configuration(self.tbl_document, table_document)
                
            
    def fill_tab_om(self):
        """ Fill tab 'O&M' (event) """
        
        table_event_node = "v_ui_om_visit_x_node"     
        self.fill_tbl_event(self.tbl_event, self.schema_name + "." + table_event_node, self.filter)
        self.tbl_event.doubleClicked.connect(self.open_selected_document_event)
        self.set_configuration(self.tbl_event, table_event_node)
        
            
    def fill_tab_scada(self):
        """ Fill tab 'Scada' """
        pass
        
        
    def fill_tab_cost(self):
        """ Fill tab 'Cost' """
              
        table_costs = "v_plan_node"        
        self.fill_table(self.tbl_costs, self.schema_name + "." + table_costs, self.filter)
        self.set_configuration(self.tbl_costs, table_costs)
                                
    