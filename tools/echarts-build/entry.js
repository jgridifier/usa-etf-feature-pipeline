// ECharts 6.1.0 custom build for the static site (hub pages + Explorer). No CDN at runtime.
import * as echarts from 'echarts/core';
import { LineChart, BarChart, ScatterChart, HeatmapChart, CustomChart } from 'echarts/charts';
import {
  GridComponent, TooltipComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, MarkPointComponent,
  DatasetComponent, AriaComponent, DataZoomComponent, VisualMapComponent, TitleComponent, GraphicComponent,
} from 'echarts/components';
import { SVGRenderer, CanvasRenderer } from 'echarts/renderers';
import { LabelLayout, UniversalTransition } from 'echarts/features';

echarts.use([
  LineChart, BarChart, ScatterChart, HeatmapChart, CustomChart,
  GridComponent, TooltipComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, MarkPointComponent,
  DatasetComponent, AriaComponent, DataZoomComponent, VisualMapComponent, TitleComponent, GraphicComponent,
  SVGRenderer, CanvasRenderer, LabelLayout, UniversalTransition,
]);
(typeof window !== 'undefined' ? window : globalThis).echarts = echarts;
