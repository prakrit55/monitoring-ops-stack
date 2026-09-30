package com.ltp.ordermanagement;

import io.micrometer.core.instrument.Meter;
import io.micrometer.core.instrument.Tag;
import io.micrometer.core.instrument.config.MeterFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.ArrayList;
import java.util.List;

@Configuration
public class MetricsConfig {

    /**
     * MeterFilter to ensure label consistency by exposing 'status_code' alongside
     * 'status' on 'http.server.requests' metrics.
     */
    @Bean
    public MeterFilter addStatusCodeTagMeterFilter() {
        return new MeterFilter() {
            @Override
            public Meter.Id map(Meter.Id id) {
                if ("http.server.requests".equals(id.getName())) {
                    String status = id.getTag("status");
                    if (status != null && id.getTag("status_code") == null) {
                        List<Tag> tags = new ArrayList<>();
                        id.getTags().forEach(tags::add);
                        tags.add(Tag.of("status_code", status));
                        return id.replaceTags(tags);
                    }
                }
                return id;
            }
        };
    }
}
