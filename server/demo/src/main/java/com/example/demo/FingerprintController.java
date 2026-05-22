package com.example.demo;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.MediaType;
import com.machinezoo.sourceafis.*;
import java.util.*;
import java.util.Base64;

@RestController
@RequestMapping("/fingerprint")
public class FingerprintController {

    @PostMapping(value="/template", consumes=MediaType.APPLICATION_OCTET_STREAM_VALUE)
    public byte[] createTemplate(@RequestBody byte[] imageBytes) {
        FingerprintTemplate template = new FingerprintTemplate(new FingerprintImage(imageBytes));
        return template.toByteArray();
    }

    @PostMapping(value="/match", consumes=MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> match(@RequestBody Map<String, String> request) {
        byte[] probeBytes = Base64.getDecoder().decode(request.get("probe"));
        byte[] candidateBytes = Base64.getDecoder().decode(request.get("candidate"));

        FingerprintTemplate probe = new FingerprintTemplate(probeBytes);
        FingerprintTemplate candidate = new FingerprintTemplate(candidateBytes);

        FingerprintMatcher matcher = new FingerprintMatcher(probe);
        double score = matcher.match(candidate);

        Map<String, Object> result = new HashMap<>();
        result.put("score", score);
        result.put("match", score >= 40); // prag SourceAFIS
        return result;
    }
}
