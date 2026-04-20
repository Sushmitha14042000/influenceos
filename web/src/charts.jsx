import { Line, Bar, Doughnut } from 'react-chartjs-2';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    ArcElement,
    Tooltip,
    Legend,
} from 'chart.js';

ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    ArcElement,
    Tooltip,
    Legend
);

export function LineChart({ data }) {
    const chartData = {
        labels: data.map((d) => d.date),
        datasets: [
            {
                label: 'Engagement',
                data: data.map((d) => d.engagement),
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59,130,246,0.2)',
                tension: 0.3,
                fill: true,
            },
        ],
    };
    return <Line data={chartData} options={{ responsive: true, plugins: { legend: { display: false } } }} height={120} />;
}

export function BarChart({ data }) {
    const chartData = {
        labels: data.map((d) => d.url),
        datasets: [
            {
                label: 'Views',
                data: data.map((d) => d.views),
                backgroundColor: '#f59e42',
            },
            {
                label: 'Likes',
                data: data.map((d) => d.likes),
                backgroundColor: '#3b82f6',
            },
            {
                label: 'Comments',
                data: data.map((d) => d.comments),
                backgroundColor: '#10b981',
            },
        ],
    };
    return <Bar data={chartData} options={{ responsive: true, plugins: { legend: { position: 'top' } } }} height={120} />;
}

export function DonutChart({ data }) {
    const chartData = {
        labels: data.map((d) => d.label),
        datasets: [
            {
                data: data.map((d) => d.value),
                backgroundColor: ['#3b82f6', '#f59e42'],
            },
        ],
    };
    return <Doughnut data={chartData} options={{ responsive: true, plugins: { legend: { position: 'bottom' } } }} height={120} />;
}
