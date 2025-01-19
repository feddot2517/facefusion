# Fork
Added REST API integration:

```
$ python facefusion.py api-run
```

for settings params look at facefusion/api.py

## Javscript Client

```typescript
import axios from 'axios';
import FormData from 'form-data';
import { FaceFusionParams, FaceFusionError } from '../types';

export class FaceFusionService {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://127.0.0.1:8081') {
    this.baseUrl = baseUrl;
  }

  async checkHealth(): Promise<boolean> {
    try {
      const response = await axios.get(`${this.baseUrl}/health`);
      return response.data.status === 'healthy';
    } catch (error) {
      console.error('Health check failed:', error);
      return false;
    }
  }

  async processImages(
    sourceFile: Buffer,
    targetFile: Buffer,
    params?: FaceFusionParams,
  ): Promise<Buffer | FaceFusionError> {
    try {
      const formData = new FormData();

      // Добавляем файлы в formData
      formData.append('source', sourceFile, {
        filename: 'source.jpg',
        contentType: 'image/jpeg',
      });

      formData.append('target', targetFile, {
        filename: 'target.jpg',
        contentType: 'image/jpeg',
      });

      // Если есть дополнительные параметры, добавляем их
      if (params) {
        formData.append('params', JSON.stringify(params));
      }

      const response = await axios.post(`${this.baseUrl}/process`, formData, {
        headers: {
          ...formData.getHeaders(),
        },
        responseType: 'arraybuffer',
        validateStatus: status => status < 500,
      });

      if (response.status !== 200) {
        // Если ошибка, преобразуем ответ в текст и парсим как JSON
        const errorText = new TextDecoder().decode(response.data);
        const errorJson = JSON.parse(errorText);
        return errorJson as FaceFusionError;
      }

      return Buffer.from(response.data);
    } catch (error) {
      console.error('Processing failed:', error);
      return {
        error: 'Processing failed',
        message: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
}

```

FaceFusion
==========

> Industry leading face manipulation platform.

[![Build Status](https://img.shields.io/github/actions/workflow/status/facefusion/facefusion/ci.yml.svg?branch=master)](https://github.com/facefusion/facefusion/actions?query=workflow:ci)
[![Coverage Status](https://img.shields.io/coveralls/facefusion/facefusion.svg)](https://coveralls.io/r/facefusion/facefusion)
![License](https://img.shields.io/badge/license-MIT-green)


Preview
-------

![Preview](https://raw.githubusercontent.com/facefusion/facefusion/master/.github/preview.png?sanitize=true)


Installation
------------

Be aware, the [installation](https://docs.facefusion.io/installation) needs technical skills and is not recommended for beginners. In case you are not comfortable using a terminal, our [Windows Installer](http://windows-installer.facefusion.io) and [macOS Installer](http://macos-installer.facefusion.io) get you started.


Usage
-----

Run the command:

```
python facefusion.py [commands] [options]

options:
  -h, --help                                      show this help message and exit
  -v, --version                                   show program's version number and exit

commands:
    run                                           run the program
    headless-run                                  run the program in headless mode
    batch-run                                     run the program in batch mode
    force-download                                force automate downloads and exit
    job-list                                      list jobs by status
    job-create                                    create a drafted job
    job-submit                                    submit a drafted job to become a queued job
    job-submit-all                                submit all drafted jobs to become a queued jobs
    job-delete                                    delete a drafted, queued, failed or completed job
    job-delete-all                                delete all drafted, queued, failed and completed jobs
    job-add-step                                  add a step to a drafted job
    job-remix-step                                remix a previous step from a drafted job
    job-insert-step                               insert a step to a drafted job
    job-remove-step                               remove a step from a drafted job
    job-run                                       run a queued job
    job-run-all                                   run all queued jobs
    job-retry                                     retry a failed job
    job-retry-all                                 retry all failed jobs
```


Documentation
-------------

Read the [documentation](https://docs.facefusion.io) for a deep dive.
