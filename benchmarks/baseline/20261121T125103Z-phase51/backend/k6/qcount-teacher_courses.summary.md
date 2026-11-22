# k6 summary

scenario: teacher_courses

- http_req_duration{expected_response:true}: min=19.227, med=42.924, max=46.377, p(90)=44.483, p(95)=45.624, p(99)=46.226, avg=39.223
- vus: min=1.000, max=1.000
- http_req_connecting: p(95)=0.003, p(99)=0.056, avg=0.003, min=0.000, med=0.000, max=0.069, p(90)=0.000
- http_req_waiting: avg=39.122, min=19.173, med=42.846, max=46.279, p(90)=44.374, p(95)=45.529, p(99)=46.129
- http_req_duration: avg=39.223, min=19.227, med=42.924, max=46.377, p(90)=44.483, p(95)=45.624, p(99)=46.226
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_blocked: p(95)=0.023, p(99)=0.086, avg=0.016, min=0.003, med=0.011, max=0.102, p(90)=0.018
- http_req_sending: med=0.042, max=0.341, p(90)=0.057, p(95)=0.077, p(99)=0.288, avg=0.055, min=0.012
- iterations: count=20.000, rate=4.164
- http_req_receiving: p(95)=0.063, p(99)=0.066, avg=0.046, min=0.033, med=0.043, max=0.067, p(90)=0.056
- http_req_failed: rate=0.000
