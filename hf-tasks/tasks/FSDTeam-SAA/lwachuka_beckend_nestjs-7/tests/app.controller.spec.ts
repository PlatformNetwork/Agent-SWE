import { Test } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { AppController } from './app.controller';
import { AppService } from './app.service';

describe('AppController (unit)', () => {
  let app: INestApplication;
  let appService: AppService;

  beforeEach(async () => {
    const moduleRef = await Test.createTestingModule({
      controllers: [AppController],
      providers: [AppService],
    }).compile();

    app = moduleRef.createNestApplication();
    await app.init();

    appService = moduleRef.get(AppService);
  });

  afterEach(async () => {
    await app.close();
  });

  it('responds with HTML and returns the full status page', async () => {
    const response = await request(app.getHttpServer()).get('/').expect(200);

    expect(response.headers['content-type']).toMatch(/text\/html/);

    const expectedBody = appService.getHello();
    expect(response.text).toBe(expectedBody);
    expect(response.text).toContain('<html>');
    expect(response.text).toContain('<title>');
  });

  it('keeps the service HTML payload consistent', async () => {
    const html = appService.getHello();

    expect(html.trim().startsWith('<html>')).toBe(true);
    expect(html).toContain('Server is running');
    expect(html).toMatch(/<body>[\s\S]*<\/body>/);
  });
});
