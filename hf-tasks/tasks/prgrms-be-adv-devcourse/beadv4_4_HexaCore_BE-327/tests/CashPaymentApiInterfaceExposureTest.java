package com.back.cash;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Arrays;

import static org.assertj.core.api.Assertions.assertThat;

class CashPaymentApiInterfaceExposureTest {

    @Test
    @DisplayName("결제 컨트롤러는 스웨거 노출 인터페이스를 구현한다")
    void controllerImplementsSwaggerInterface() throws Exception {
        Class<?> controllerClass = Class.forName("com.back.cash.adapter.in.ApiV1CashPaymentController");
        Class<?> apiInterface = Class.forName("com.back.cash.adapter.in.CashPaymentApiV1");

        boolean implementsInterface = Arrays.asList(controllerClass.getInterfaces()).contains(apiInterface);

        assertThat(implementsInterface).isTrue();
    }
}
