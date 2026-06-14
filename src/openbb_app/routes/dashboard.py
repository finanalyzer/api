import logging
import threading
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi import Path as FastAPIPath
from fastapi import Query
from pydantic import BaseModel, Field

from openbb_app.core.database import DatabaseManager
from openbb_app.core.registry import register_widget

logger = logging.getLogger(__name__)

# 创建路由器
dashboard_router = APIRouter()

# Per-dashboard locks to prevent read-modify-write race conditions
_dashboard_locks: dict[str, threading.Lock] = {}
_lock_registry_lock = threading.Lock()


def _get_dashboard_lock(dashboard_id: str) -> threading.Lock:
    """Get or create a lock for a specific dashboard."""
    with _lock_registry_lock:
        if dashboard_id not in _dashboard_locks:
            _dashboard_locks[dashboard_id] = threading.Lock()
        return _dashboard_locks[dashboard_id]


# 初始化数据库管理器
def get_db_manager() -> DatabaseManager:
    """获取数据库管理器"""
    from openbb_core.app.service.user_service import UserService
    from pathlib import Path

    # 读取用户设置
    settings = UserService.read_from_file()
    cache_dir = Path(settings.preferences.cache_directory)

    logger.info(f"Using cache directory: {cache_dir}")

    # 在数据目录下创建SQLite数据库
    db_path = cache_dir / "appdata/equity.db"
    return DatabaseManager(db_path)


# Pydantic模型
class WidgetBase(BaseModel):
    id: str = Field(..., description="Widget ID")
    type: str = Field(..., description="Widget type")
    title: str = Field(..., description="Widget title")
    position: dict = Field(..., description="Widget position and size")
    data: Optional[dict] = Field(None, description="Widget data")


class WidgetCreate(WidgetBase):
    pass


class WidgetUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Widget title")
    position: Optional[dict] = Field(None, description="Widget position and size")
    data: Optional[dict] = Field(None, description="Widget data")


class WidgetResponse(WidgetBase):
    class Config:
        from_attributes = True


class TabBase(BaseModel):
    id: str = Field(..., description="Tab ID")
    name: str = Field(..., description="Tab name")
    icon: Optional[str] = Field(None, description="Tab icon")


class DashboardBase(BaseModel):
    id: str = Field(..., description="Dashboard ID")
    name: str = Field(..., description="Dashboard name")
    description: Optional[str] = Field(None, description="Dashboard description")
    widgets: List[WidgetBase] = Field(default_factory=list, description="Dashboard widgets")
    tabs: List[TabBase] = Field(default_factory=list, description="Dashboard tabs")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Update timestamp")


class DashboardCreate(DashboardBase):
    pass


class DashboardUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Dashboard name")
    description: Optional[str] = Field(None, description="Dashboard description")
    widgets: Optional[List[WidgetBase]] = Field(None, description="Dashboard widgets")
    tabs: Optional[List[TabBase]] = Field(None, description="Dashboard tabs")


class DashboardResponse(DashboardBase):
    class Config:
        from_attributes = True


# Dashboard API endpoints
@register_widget(
    {
        "name": "Dashboard List",
        "description": "List all dashboards",
        "type": "table",
        "category": "Dashboard",
        "widgetId": "dashboard/list",
        "endpoint": "/v1/dashboard",
        "runButton": True,
        "gridData": {"w": 50, "h": 20},
        "data": {
            "dataKey": "",
            "table": {
                "showAll": True,
                "enableAdvanced": True,
                "columnsDefs": [
                    {
                        "field": "id",
                        "headerName": "ID",
                        "headerTooltip": "Dashboard ID",
                        "cellDataType": "text",
                        "pinned": "left",
                    },
                    {
                        "field": "name",
                        "headerName": "Name",
                        "headerTooltip": "Dashboard name",
                        "cellDataType": "text",
                    },
                    {
                        "field": "description",
                        "headerName": "Description",
                        "headerTooltip": "Dashboard description",
                        "cellDataType": "text",
                    },
                    {
                        "field": "widgets",
                        "headerName": "Widgets",
                        "headerTooltip": "Number of widgets",
                        "cellDataType": "number",
                        "valueGetter": "params.data.widgets.length",
                    },
                    {
                        "field": "created_at",
                        "headerName": "Created At",
                        "headerTooltip": "Creation timestamp",
                        "cellDataType": "text",
                    },
                    {
                        "field": "updated_at",
                        "headerName": "Updated At",
                        "headerTooltip": "Update timestamp",
                        "cellDataType": "text",
                    },
                ],
            },
        },
        "source": ["Dashboard"],
        "params": [],
    }
)
@dashboard_router.get("/dashboard", response_model=List[DashboardResponse])
def get_all_dashboards():
    """获取所有仪表盘"""
    try:
        db_manager = get_db_manager()
        dashboards = db_manager.get_all_dashboards()
        return dashboards
    except Exception as e:
        logger.error(f"Error getting all dashboards: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboards")


@dashboard_router.get("/dashboard/{dashboard_id}", response_model=DashboardResponse)
def get_dashboard(dashboard_id: str = FastAPIPath(..., description="仪表盘ID")):
    """获取单个仪表盘"""
    try:
        db_manager = get_db_manager()
        dashboard = db_manager.get_dashboard(dashboard_id)
        if not dashboard:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return dashboard
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard")


@dashboard_router.post("/dashboard", response_model=DashboardResponse)
def create_dashboard(dashboard: DashboardCreate):
    """创建新的仪表盘"""
    try:
        db_manager = get_db_manager()
        dashboard_data = dashboard.model_dump()
        db_manager.add_dashboard(dashboard_data)
        created_dashboard = db_manager.get_dashboard(dashboard.id)
        if not created_dashboard:
            raise HTTPException(status_code=500, detail="Failed to create dashboard")
        return created_dashboard
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to create dashboard")


@dashboard_router.put("/dashboard/{dashboard_id}", response_model=DashboardResponse)
def update_dashboard(
    dashboard: DashboardUpdate, dashboard_id: str = FastAPIPath(..., description="仪表盘ID")
):
    """更新仪表盘信息"""
    try:
        db_manager = get_db_manager()
        existing_dashboard = db_manager.get_dashboard(dashboard_id)
        if not existing_dashboard:
            raise HTTPException(status_code=404, detail="Dashboard not found")

        dashboard_data = dashboard.model_dump(exclude_unset=True)
        db_manager.update_dashboard(dashboard_id, dashboard_data)
        updated_dashboard = db_manager.get_dashboard(dashboard_id)
        if not updated_dashboard:
            raise HTTPException(status_code=500, detail="Failed to update dashboard")
        return updated_dashboard
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to update dashboard")


@dashboard_router.delete("/dashboard/{dashboard_id}")
def delete_dashboard(dashboard_id: str = FastAPIPath(..., description="仪表盘ID")):
    """删除仪表盘"""
    try:
        db_manager = get_db_manager()
        success = db_manager.delete_dashboard(dashboard_id)
        if not success:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return {"message": "Dashboard deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete dashboard")


# Widget API endpoints
@dashboard_router.get("/dashboard/{dashboard_id}/widgets", response_model=List[WidgetResponse])
def get_dashboard_widgets(dashboard_id: str = FastAPIPath(..., description="仪表盘ID")):
    """获取仪表盘的所有组件"""
    try:
        db_manager = get_db_manager()
        dashboard = db_manager.get_dashboard(dashboard_id)
        if not dashboard:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return dashboard.get("widgets", [])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard widgets: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard widgets")


@dashboard_router.post("/dashboard/{dashboard_id}/widgets", response_model=WidgetResponse)
def add_dashboard_widget(
    widget: WidgetCreate, dashboard_id: str = FastAPIPath(..., description="仪表盘ID")
):
    """向仪表盘添加组件"""
    try:
        lock = _get_dashboard_lock(dashboard_id)
        with lock:
            db_manager = get_db_manager()
            dashboard = db_manager.get_dashboard(dashboard_id)
            if not dashboard:
                raise HTTPException(status_code=404, detail="Dashboard not found")

            widgets = dashboard.get("widgets", [])
            widgets.append(widget.model_dump())
            db_manager.update_dashboard(dashboard_id, {"widgets": widgets})
        return widget
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding dashboard widget: {e}")
        raise HTTPException(status_code=500, detail="Failed to add dashboard widget")


@dashboard_router.put("/dashboard/{dashboard_id}/widgets/{widget_id:path}", response_model=WidgetResponse)
def update_dashboard_widget(
    widget: WidgetUpdate,
    dashboard_id: str = FastAPIPath(..., description="仪表盘ID"),
    widget_id: str = FastAPIPath(..., description="组件ID"),
):
    """更新仪表盘组件"""
    try:
        lock = _get_dashboard_lock(dashboard_id)
        with lock:
            db_manager = get_db_manager()
            dashboard = db_manager.get_dashboard(dashboard_id)
            if not dashboard:
                raise HTTPException(status_code=404, detail="Dashboard not found")

            widgets = dashboard.get("widgets", [])
            widget_index = next((i for i, w in enumerate(widgets) if w.get("id") == widget_id), -1)
            if widget_index == -1:
                raise HTTPException(status_code=404, detail="Widget not found")

            widget_data = widget.model_dump(exclude_unset=True)
            widgets[widget_index] = {**widgets[widget_index], **widget_data}
            db_manager.update_dashboard(dashboard_id, {"widgets": widgets})
            result = widgets[widget_index]
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating dashboard widget: {e}")
        raise HTTPException(status_code=500, detail="Failed to update dashboard widget")


@dashboard_router.delete("/dashboard/{dashboard_id}/widgets/{widget_id:path}")
def delete_dashboard_widget(
    dashboard_id: str = FastAPIPath(..., description="仪表盘ID"),
    widget_id: str = FastAPIPath(..., description="组件ID"),
):
    """删除仪表盘组件"""
    try:
        lock = _get_dashboard_lock(dashboard_id)
        with lock:
            db_manager = get_db_manager()
            dashboard = db_manager.get_dashboard(dashboard_id)
            if not dashboard:
                raise HTTPException(status_code=404, detail="Dashboard not found")

            widgets = dashboard.get("widgets", [])
            widget_index = next((i for i, w in enumerate(widgets) if w.get("id") == widget_id), -1)
            if widget_index == -1:
                raise HTTPException(status_code=404, detail="Widget not found")

            widgets.pop(widget_index)
            db_manager.update_dashboard(dashboard_id, {"widgets": widgets})
        return {"message": "Widget deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dashboard widget: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete dashboard widget")
