<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Symfony\Component\Process\Exception\ProcessFailedException;
use Symfony\Component\Process\Process;
use Illuminate\Support\Facades\Log;

class CrawlWebsitePython extends Command
{
    protected $signature = 'crawl:website-python {url}';
    protected $description = 'Crawl a website using a Python script and retrieve all URLs';

    public function handle()
    {
        $url = $this->argument('url');
        $pythonScriptPath = base_path('scripts/crawlerjs.py');

        Log::info('Starting Python process for URL: ' . $url);
        Log::info('Python script path: ' . $pythonScriptPath);

        $process = new Process(['python', $pythonScriptPath, $url]);
        $process->setTimeout(3600); // Set a timeout to prevent indefinite hanging
        $process->start();

        $process->wait(function ($type, $buffer) {
            if (Process::ERR === $type) {
                Log::error($buffer);
                $this->error($buffer);
            } else {
                // Eliminar las secuencias de escape ANSI para los registros
                $cleanBuffer = preg_replace('/\033\[.*?m/', '', $buffer);
                Log::info($cleanBuffer);
                $this->line($buffer); // Usar $this->line() para mantener los colores ANSI
            }
        });

        if (!$process->isSuccessful()) {
            throw new ProcessFailedException($process);
        }

        Log::info('Python proceso completado');
        $this->info('Python proceso completado');
    }
}

