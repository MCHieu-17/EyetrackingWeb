# k6 summary

scenario: teacher_courses

- http_req_duration{expected_response:true}: min=2.573, med=7.887, max=16.628, p(90)=11.309, p(95)=12.356, p(99)=16.623, avg=8.238
- vus: min=2.000, max=2.000
- http_req_receiving: p(99)=0.357, avg=0.093, min=0.011, med=0.054, max=0.397, p(90)=0.199, p(95)=0.284
- http_req_connecting: avg=0.003, min=0.000, med=0.000, max=0.140, p(90)=0.000, p(95)=0.000, p(99)=0.131
- http_req_waiting: min=2.517, med=7.799, max=16.505, p(90)=11.133, p(95)=12.179, p(99)=16.505, avg=8.101
- http_req_blocked: avg=0.015, min=0.002, med=0.011, max=0.196, p(90)=0.014, p(95)=0.023, p(99)=0.196
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_sending: max=0.163, p(90)=0.062, p(95)=0.068, p(99)=0.124, avg=0.043, min=0.008, med=0.042
- iterations: count=96.000, rate=9.561
- http_req_duration: p(99)=16.623, avg=8.238, min=2.573, med=7.887, max=16.628, p(90)=11.309, p(95)=12.356
- http_req_failed: rate=0.000
