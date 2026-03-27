package com.ott.core.modules.preference.service;

import com.ott.common.persistence.entity.Tag;
import com.ott.common.persistence.entity.User;
import com.ott.common.persistence.entity.UserPreference;
import com.ott.common.persistence.enums.UserRole;
import com.ott.core.modules.preference.dto.TagScoreDto;
import com.ott.core.modules.preference.repository.UserPreferenceRepository;
import com.ott.core.modules.tag.repository.VideoTagRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.DefaultTypedTuple;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class UserPreferenceServiceTest {

    @Mock
    private UserPreferenceRepository userPreferenceRepository;

    @Mock
    private VideoTagRepository videoTagRepository;

    @Mock
    private StringRedisTemplate stringRedisTemplate;

    @Mock
    private ZSetOperations<String, String> zSetOperations;

    private UserPreferenceService userPreferenceService;

    @BeforeEach
    void setUp() {
        userPreferenceService = new UserPreferenceService(userPreferenceRepository, videoTagRepository, stringRedisTemplate);
        when(stringRedisTemplate.opsForZSet()).thenReturn(zSetOperations);
    }

    @Test
    @DisplayName("Redis 캐시 히트 시 DB 조회 없이 결과 반환")
    void getTopPreferences_cacheHit_returnsRedisData() {
        Long userId = 42L;
        String key = "user:" + userId + ":preference";

        Set<ZSetOperations.TypedTuple<String>> redisResult = new LinkedHashSet<>(List.of(
                new DefaultTypedTuple<>("action", 4.5),
                new DefaultTypedTuple<>("comedy", 2.0)
        ));

        when(zSetOperations.reverseRangeWithScores(eq(key), eq(0L), eq(1L))).thenReturn(redisResult);

        List<TagScoreDto> result = userPreferenceService.getTopPreferences(userId, 2);

        assertThat(result).hasSize(2);
        assertThat(result.get(0).tagName()).isEqualTo("action");
        assertThat(result.get(0).score()).isEqualTo(4.5);
        assertThat(result.get(1).tagName()).isEqualTo("comedy");
        assertThat(result.get(1).score()).isEqualTo(2.0);

        verify(userPreferenceRepository, never()).findWithTagByUserId(anyLong());
    }

    @Test
    @DisplayName("Redis 캐시 미스 시 DB에서 복구 후 점수 내림차순으로 제한")
    void getTopPreferences_cacheMiss_recoversAndSorts() {
        Long userId = 7L;
        String key = "user:" + userId + ":preference";

        when(zSetOperations.reverseRangeWithScores(eq(key), eq(0L), eq(1L))).thenReturn(Set.of());

        User user = new User("user@example.com", "nickname", "hash", UserRole.VIEWER);
        Tag tagLow = new Tag("drama");
        Tag tagHigh = new Tag("thriller");
        Tag tagMid = new Tag("history");

        UserPreference prefLow = new UserPreference(user, tagLow, 1.2);
        UserPreference prefHigh = new UserPreference(user, tagHigh, 4.1);
        UserPreference prefMid = new UserPreference(user, tagMid, 2.6);

        when(userPreferenceRepository.findWithTagByUserId(userId))
                .thenReturn(List.of(prefLow, prefHigh, prefMid));

        List<TagScoreDto> result = userPreferenceService.getTopPreferences(userId, 2);

        assertThat(result).hasSize(2);
        assertThat(result.get(0).tagName()).isEqualTo("thriller");
        assertThat(result.get(0).score()).isEqualTo(4.1);
        assertThat(result.get(1).tagName()).isEqualTo("history");
        assertThat(result.get(1).score()).isEqualTo(2.6);

        verify(zSetOperations).add(key, "drama", 1.2);
        verify(zSetOperations).add(key, "thriller", 4.1);
        verify(zSetOperations).add(key, "history", 2.6);
    }

    @Test
    @DisplayName("DB에도 취향 데이터 없으면 빈 리스트 반환")
    void getTopPreferences_cacheMiss_emptyDb() {
        Long userId = 15L;
        String key = "user:" + userId + ":preference";

        when(zSetOperations.reverseRangeWithScores(eq(key), eq(0L), eq(2L))).thenReturn(Set.of());
        when(userPreferenceRepository.findWithTagByUserId(userId)).thenReturn(List.of());

        List<TagScoreDto> result = userPreferenceService.getTopPreferences(userId, 3);

        assertThat(result).isEmpty();

        verify(zSetOperations, never()).add(eq(key), anyString(), anyDouble());
    }
}
