package com.late.donot.calculator.controller;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.late.donot.calculator.model.service.CalculatorService;
import com.late.donot.common.config.DBconfig;
import com.late.donot.common.config.EmailConfig;
import com.late.donot.common.config.FileConfig;
import com.late.donot.common.config.InterceptorConfig;
import com.late.donot.common.interceptor.LoginCheckInterceptor;
import com.late.donot.member.model.dto.Member;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.FilterType;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(
    controllers = CalculatorController.class,
    excludeFilters = @ComponentScan.Filter(
        type = FilterType.ASSIGNABLE_TYPE,
        classes = {
            FileConfig.class,
            DBconfig.class,
            EmailConfig.class,
            InterceptorConfig.class,
            LoginCheckInterceptor.class
        }
    )
)
@AutoConfigureMockMvc(addFilters = false)
class CalculatorPushSaveControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private CalculatorService calculatorService;

    @Test
    void savePushRequiresLogin() throws Exception {
        String payload = "{\"pushName\":\"Morning Run\",\"transportType\":\"BUS\",\"arriveTime\":35,\"prepareTime\":15,\"spareTime\":5,\"pushTime\":50,\"dayOfWeek\":\"FRI\",\"startName\":\"Station A\",\"startLat\":37.5,\"startLng\":127.01,\"endName\":\"Station B\",\"endLat\":37.6,\"endLng\":127.02,\"routeNo\":3,\"startStation\":\"Alpha\",\"endStation\":\"Beta\"}";

        mockMvc.perform(post("/calculator/push/save")
                .contentType(MediaType.APPLICATION_JSON)
                .content(payload))
            .andExpect(status().isOk())
            .andExpect(content().string("0"));
    }

    @Test
    void savePushWithSessionReturnsResponse() throws Exception {
        String payload = "{\"pushName\":\"Evening Class\",\"transportType\":\"SUBWAY\",\"arriveTime\":42,\"prepareTime\":12,\"spareTime\":8,\"pushTime\":62,\"dayOfWeek\":\"MON\",\"startName\":\"Campus\",\"startLat\":37.45,\"startLng\":126.97,\"endName\":\"Library\",\"endLat\":37.47,\"endLng\":126.99,\"routeNo\":7,\"startStation\":\"Gamma\",\"endStation\":\"Delta\"}";

        MockHttpSession session = new MockHttpSession();
        session.setAttribute("loginMember", Member.builder().memberNo(17).memberName("Tester").build());

        mockMvc.perform(post("/calculator/push/save")
                .session(session)
                .contentType(MediaType.APPLICATION_JSON)
                .content(payload))
            .andExpect(status().isOk())
            .andExpect(content().string("0"));
    }
}
