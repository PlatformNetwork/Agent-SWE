const path = require('path');

describe('recalculateOnAttendanceUpdate employee lookup', () => {
  beforeEach(() => {
    jest.resetModules();
  });

  test('uses uppercase emp_no without is_active filter', async () => {
    const findOneMock = jest.fn().mockResolvedValue(null);

    jest.doMock('../../employees/model/Employee', () => ({
      findOne: findOneMock,
    }));

    jest.isolateModules(() => {
      const { recalculateOnAttendanceUpdate } = require('../../attendance/services/summaryCalculationService');

      return recalculateOnAttendanceUpdate('ab123', '2024-02-15');
    });

    // allow async module call to complete
    await new Promise(process.nextTick);

    expect(findOneMock).toHaveBeenCalledTimes(1);
    expect(findOneMock).toHaveBeenCalledWith({ emp_no: 'AB123' });
  });
});
