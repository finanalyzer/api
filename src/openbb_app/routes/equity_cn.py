from fastapi import APIRouter, Query
from openbb_app.core.registry import register_widget
import pandas as pd
from typing import List
import json
import asyncio
import numpy as np
from fastapi import Depends


equity_cn_router = APIRouter()
