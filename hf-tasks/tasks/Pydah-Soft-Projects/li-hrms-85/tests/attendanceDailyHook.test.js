const path = require('path');

describe('AttendanceDaily post findOneAndUpdate hook', () => {
  beforeEach(() => {
    jest.resetModules();
  });

  test('registers a post hook for findOneAndUpdate', () => {
    const AttendanceDaily = require('../../attendance/model/AttendanceDaily');
    const posts = AttendanceDaily.schema.s.hooks._posts.get('findOneAndUpdate');

    expect(posts).toBeDefined();
    expect(Array.isArray(posts)).toBe(true);
    expect(posts.length).toBeGreaterThan(0);
  });

  test('triggers recalculation and extra hours based on updates', async () => {
    const recalculateMock = jest.fn().mockResolvedValue();
    const detectExtraMock = jest.fn().mockResolvedValue();

    jest.doMock('../../attendance/services/summaryCalculationService', () => ({
      recalculateOnAttendanceUpdate: recalculateMock,
    }));
    jest.doMock('../../attendance/services/extraHoursService', () => ({
      detectExtraHours: detectExtraMock,
    }));

    let AttendanceDaily;
    jest.isolateModules(() => {
      AttendanceDaily = require('../../attendance/model/AttendanceDaily');
    });

    const posts = AttendanceDaily.schema.s.hooks._posts.get('findOneAndUpdate');
    const hook = posts && posts[0] && posts[0].fn;

    expect(typeof hook).toBe('function');

    // Case 1: shifts update triggers both recalculation and extra hours
    await hook.call({
      getQuery: () => ({ employeeNumber: 'EMP9', date: '2024-03-20' }),
      getUpdate: () => ({ $set: { shifts: [{ shiftNumber: 1 }] } }),
    });

    expect(recalculateMock).toHaveBeenCalledWith('EMP9', '2024-03-20');
    expect(detectExtraMock).toHaveBeenCalledWith('EMP9', '2024-03-20');

    recalculateMock.mockClear();
    detectExtraMock.mockClear();

    // Case 2: status update triggers recalculation only
    await hook.call({
      getQuery: () => ({ employeeNumber: 'EMP9', date: '2024-03-21' }),
      getUpdate: () => ({ $set: { status: 'ABSENT' } }),
    });

    expect(recalculateMock).toHaveBeenCalledWith('EMP9', '2024-03-21');
    expect(detectExtraMock).not.toHaveBeenCalled();

    recalculateMock.mockClear();
    detectExtraMock.mockClear();

    // Case 3: unrelated update triggers nothing
    await hook.call({
      getQuery: () => ({ employeeNumber: 'EMP9', date: '2024-03-22' }),
      getUpdate: () => ({ $set: { note: 'updated' } }),
    });

    expect(recalculateMock).not.toHaveBeenCalled();
    expect(detectExtraMock).not.toHaveBeenCalled();
  });
});
