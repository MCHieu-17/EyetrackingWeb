# k6 summary

scenario: course_visits

- http_req_blocked: avg=0.017, min=0.005, med=0.012, max=0.121, p(90)=0.015, p(95)=0.023, p(99)=0.101
- http_req_duration: min=3.523, med=12.618, max=26.776, p(90)=15.492, p(95)=16.057, p(99)=24.632, avg=12.011
- http_req_duration{expected_response:true}: avg=12.011, min=3.523, med=12.618, max=26.776, p(90)=15.492, p(95)=16.057, p(99)=24.632
- vus: min=1.000, max=1.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: p(99)=24.339, avg=11.675, min=3.338, med=12.139, max=26.526, p(90)=14.929, p(95)=15.590
- http_req_sending: max=0.073, p(90)=0.052, p(95)=0.053, p(99)=0.069, avg=0.043, min=0.012, med=0.043
- http_req_receiving: avg=0.293, min=0.068, med=0.276, max=0.532, p(90)=0.519, p(95)=0.522, p(99)=0.530
- http_req_failed: rate=0.000
- iterations: rate=4.692, count=20.000
- http_req_connecting: max=0.086, p(90)=0.000, p(95)=0.004, p(99)=0.069, avg=0.004, min=0.000, med=0.000
