# k6 summary

scenario: teacher_courses

- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_duration: avg=37.250, min=18.862, med=40.450, max=62.823, p(90)=45.384, p(95)=50.147, p(99)=54.990
- http_req_blocked: p(99)=0.097, avg=0.014, min=0.002, med=0.011, max=0.111, p(90)=0.014, p(95)=0.016
- iterations: count=84.000, rate=8.398
- http_req_receiving: avg=0.047, min=0.014, med=0.044, max=0.197, p(90)=0.067, p(95)=0.082, p(99)=0.112
- http_req_sending: max=0.064, p(90)=0.052, p(95)=0.055, p(99)=0.062, avg=0.042, min=0.007, med=0.043
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: max=62.823, p(90)=45.384, p(95)=50.147, p(99)=54.990, avg=37.250, min=18.862, med=40.450
- vus: min=2.000, max=2.000
- http_req_waiting: med=40.351, max=62.703, p(90)=45.301, p(95)=50.068, p(99)=54.869, avg=37.160, min=18.799
- http_req_connecting: p(99)=0.072, avg=0.002, min=0.000, med=0.000, max=0.079, p(90)=0.000, p(95)=0.000
