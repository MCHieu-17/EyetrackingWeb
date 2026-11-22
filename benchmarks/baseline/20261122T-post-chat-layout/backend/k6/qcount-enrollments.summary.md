# k6 summary

scenario: enrollments

- http_req_connecting: max=0.088, p(90)=0.000, p(95)=0.004, p(99)=0.071, avg=0.004, min=0.000, med=0.000
- http_req_duration: max=4.769, p(90)=4.628, p(95)=4.654, p(99)=4.746, avg=4.064, min=1.192, med=4.346
- iterations: count=20.000, rate=4.876
- http_req_failed: rate=0.000
- http_req_blocked: max=0.119, p(90)=0.029, p(95)=0.043, p(99)=0.104, avg=0.019, min=0.004, med=0.012
- http_req_duration{expected_response:true}: avg=4.064, min=1.192, med=4.346, max=4.769, p(90)=4.628, p(95)=4.654, p(99)=4.746
- http_req_waiting: p(99)=4.592, avg=3.900, min=1.128, med=4.191, max=4.609, p(90)=4.500, p(95)=4.528
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- vus: min=1.000, max=1.000
- http_req_sending: p(90)=0.062, p(95)=0.073, p(99)=0.079, avg=0.047, min=0.014, med=0.046, max=0.080
- http_req_receiving: p(90)=0.148, p(95)=0.175, p(99)=0.240, avg=0.118, min=0.042, med=0.107, max=0.256
