import { renderHook, act } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useActivityGallery } from './use-activity-gallery';

describe('useActivityGallery navigation', () => {
  it('wraps to last image when navigating prev from first', () => {
    const { result } = renderHook(() =>
      useActivityGallery({
        activityId: 'activity-1',
        coverImage: 'cover.jpg',
        galleryImages: ['one.jpg', 'two.jpg', 'three.jpg'],
      }),
    );

    expect(result.current.currentIndex).toBe(0);
    expect(result.current.currentSrc).toBe('one.jpg');

    act(() => {
      result.current.goPrev();
    });

    expect(result.current.currentIndex).toBe(2);
    expect(result.current.currentSrc).toBe('three.jpg');
  });

  it('wraps to first image when navigating next from last', () => {
    const { result } = renderHook(() =>
      useActivityGallery({
        activityId: 'activity-2',
        coverImage: 'cover.jpg',
        galleryImages: ['alpha.jpg', 'beta.jpg', 'gamma.jpg'],
      }),
    );

    act(() => {
      result.current.setIndex(2);
    });

    expect(result.current.currentIndex).toBe(2);
    expect(result.current.currentSrc).toBe('gamma.jpg');

    act(() => {
      result.current.goNext();
    });

    expect(result.current.currentIndex).toBe(0);
    expect(result.current.currentSrc).toBe('alpha.jpg');
  });

  it('keeps index at zero when there is only one image', () => {
    const { result } = renderHook(() =>
      useActivityGallery({
        activityId: 'activity-3',
        coverImage: 'only.jpg',
        galleryImages: [],
      }),
    );

    expect(result.current.currentIndex).toBe(0);
    expect(result.current.currentSrc).toBe('only.jpg');

    act(() => {
      result.current.goNext();
      result.current.goPrev();
    });

    expect(result.current.currentIndex).toBe(0);
    expect(result.current.currentSrc).toBe('only.jpg');
  });
});
