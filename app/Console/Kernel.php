<?php

namespace App\Console;

use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Foundation\Console\Kernel as ConsoleKernel;
use App\Console\Commands\CrawlWebsitePython;

class Kernel extends ConsoleKernel
{
    protected $commands = [
        CrawlWebsitePython::class,
    ];

    protected function schedule(Schedule $schedule)
    {
        // Define the application's command schedule.
    }

    protected function commands()
    {
        $this->load(__DIR__.'/Commands');

        require base_path('routes/console.php');
    }
}


