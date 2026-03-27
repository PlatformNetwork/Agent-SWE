package com.back.cash;

import com.back.cash.adapter.out.TossPaymentsClient;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

import java.lang.reflect.Field;
import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

class TossPaymentsClientAuthorizationCacheTest {

    private MockWebServer mockServer;
    private final JsonMapper jsonMapper = JsonMapper.builder().build();

    @BeforeEach
    void setUp() throws Exception {
        mockServer = new MockWebServer();
        mockServer.start();
    }

    @AfterEach
    void tearDown() throws Exception {
        mockServer.shutdown();
    }

    @Test
    @DisplayName("Authorization 헤더는 첫 요청 이후에도 동일한 값으로 유지된다")
    void confirm_reusesAuthorizationHeaderAfterSecretKeyMutation() throws Exception {
        // given
        mockServer.enqueue(new MockResponse().setResponseCode(200));
        mockServer.enqueue(new MockResponse().setResponseCode(200));

        TossPaymentsClient client = new TossPaymentsClient(
                "first-secret",
                mockServer.url("/").toString(),
                5000,
                5000,
                jsonMapper);

        // when
        client.confirm("pk-111", "order-111", new BigDecimal("12345"));

        try {
            Field secretKeyField = TossPaymentsClient.class.getDeclaredField("secretKey");
            secretKeyField.setAccessible(true);
            secretKeyField.set(client, "changed-secret");
        } catch (NoSuchFieldException ignored) {
            // If secretKey is removed in the patched version, we still validate header reuse.
        }

        client.confirm("pk-222", "order-222", new BigDecimal("67890"));

        // then
        RecordedRequest first = mockServer.takeRequest();
        RecordedRequest second = mockServer.takeRequest();

        assertThat(first.getHeader("Authorization")).isNotBlank();
        assertThat(second.getHeader("Authorization")).isEqualTo(first.getHeader("Authorization"));
    }

    @Test
    @DisplayName("서로 다른 시크릿 키를 사용하는 클라이언트는 다른 Authorization 헤더를 사용한다")
    void confirm_usesDifferentAuthorizationHeaderForDifferentClient() throws Exception {
        // given
        mockServer.enqueue(new MockResponse().setResponseCode(200));
        mockServer.enqueue(new MockResponse().setResponseCode(200));

        TossPaymentsClient firstClient = new TossPaymentsClient(
                "alpha-secret",
                mockServer.url("/").toString(),
                5000,
                5000,
                jsonMapper);

        TossPaymentsClient secondClient = new TossPaymentsClient(
                "beta-secret",
                mockServer.url("/").toString(),
                5000,
                5000,
                jsonMapper);

        // when
        firstClient.confirm("pk-333", "order-333", new BigDecimal("11111"));
        secondClient.confirm("pk-444", "order-444", new BigDecimal("22222"));

        // then
        RecordedRequest first = mockServer.takeRequest();
        RecordedRequest second = mockServer.takeRequest();

        assertThat(first.getHeader("Authorization")).isNotBlank();
        assertThat(second.getHeader("Authorization")).isNotBlank();
        assertThat(first.getHeader("Authorization")).isNotEqualTo(second.getHeader("Authorization"));
    }
}
