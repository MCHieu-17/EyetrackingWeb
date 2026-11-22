# k6 summary

scenario: course_visits

- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_sending: min=0.013, med=0.047, max=0.098, p(90)=0.056, p(95)=0.068, p(99)=0.092, avg=0.047
- iterations: rate=4.122, count=20.000
- http_req_duration: max=51.510, p(90)=51.014, p(95)=51.294, p(99)=51.467, avg=41.384, min=16.038, med=47.172
- http_req_receiving: avg=0.277, min=0.110, med=0.202, max=1.562, p(90)=0.336, p(95)=0.542, p(99)=1.358
- http_req_blocked: avg=0.023, min=0.003, med=0.011, max=0.262, p(90)=0.013, p(95)=0.025, p(99)=0.215
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: med=47.172, max=51.510, p(90)=51.014, p(95)=51.294, p(99)=51.467, avg=41.384, min=16.038
- http_req_waiting: p(99)=51.148, avg=41.060, min=15.810, med=46.922, max=51.237, p(90)=49.965, p(95)=50.792
- http_req_connecting: avg=0.009, min=0.000, med=0.000, max=0.176, p(90)=0.000, p(95)=0.009, p(99)=0.143
- http_req_failed: rate=0.000
